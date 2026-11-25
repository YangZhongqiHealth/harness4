"""Local, read-only ship review entry point."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from .contracts import ModelRef, UsageSummary, digest, text_digest
from .provider import ProviderFailure, complete
from .ship import Review, ShipPolicy, ShipReport, SYSTEM_PROMPT, evaluate_policy, parse_review


MAX_DIFF_BYTES = 200_000


def git(repo: str, *args: str) -> bytes:
    result = subprocess.run(['git', '-C', repo, *args], capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError('Git operation failed; check the repository and commit references.')
    return result.stdout


def collect_diff(repo: str, base: str, head: str) -> tuple[str, str, tuple[str, ...], str, int]:
    base_sha = git(repo, 'rev-parse', '--verify', '--end-of-options', base + '^{commit}').decode().strip()
    head_sha = git(repo, 'rev-parse', '--verify', '--end-of-options', head + '^{commit}').decode().strip()
    names = git(repo, 'diff', '--no-ext-diff', '--no-textconv', '--no-renames', '--name-only', '-z', base_sha, head_sha, '--')
    files = tuple(p.decode('utf-8', errors='strict') for p in names.split(b'\0') if p)
    raw = git(repo, 'diff', '--no-ext-diff', '--no-textconv', '--no-renames', '--unified=3', base_sha, head_sha, '--')
    if len(raw) > MAX_DIFF_BYTES:
        raise ValueError('Diff exceeds 200 KB. Review smaller changes; no content was sent to a model.')
    diff = raw.decode('utf-8', errors='strict')
    stats = git(repo, 'diff', '--no-ext-diff', '--no-textconv', '--no-renames', '--numstat', '-z', base_sha, head_sha, '--')
    changed_lines = 0
    for row in stats.split(b'\0'):
        if not row:
            continue
        added, removed, _ = row.split(b'\t', 2)
        if added == b'-' or removed == b'-':
            raise ValueError('Binary changes require human review; no content was sent to a model.')
        changed_lines += int(added) + int(removed)
    if any(part == '..' for p in files for part in p.split('/')):
        raise ValueError('Invalid changed path.')
    return base_sha, head_sha, files, diff, changed_lines


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog='h4', description='Open, read-only PR review and policy reports (alpha).')
    commands = root.add_subparsers(dest='command', required=True)
    ship = commands.add_parser('ship', help='Review committed changes; emit an advisory JSON report.')
    ship.add_argument('--repo', default='.')
    ship.add_argument('--base', required=True, help='Base commit/ref; for PRs use the merge base.')
    ship.add_argument('--head', default='HEAD')
    ship.add_argument('--policy', type=Path, help='Trusted operator policy JSON; do not use a PR-controlled policy.')
    ship.add_argument('--checks', choices=['passed', 'failed', 'unknown'], default='unknown', help='Operator-supplied CI evidence; not independently verified.')
    mode = ship.add_mutually_exclusive_group()
    mode.add_argument('--review-file', type=Path, help='Offline fixture JSON; always requires human review.')
    mode.add_argument('--model', help='Explicit model name; enables a paid model request.')
    ship.add_argument('--base-url', help='Explicit Chat Completions API base URL, ending in /v1.')
    ship.add_argument('--key-env', default='H4_MODEL_KEY', help='Environment variable name, never the key itself.')
    ship.add_argument('--max-output-tokens', type=int, default=4096)
    ship.add_argument('--timeout', type=float, default=60)
    doctor = commands.add_parser('doctor', help='Inspect declared model capabilities; probe only when explicitly requested.')
    doctor.add_argument('--model', required=True)
    doctor.add_argument('--base-url', required=True)
    doctor.add_argument('--key-env', default='H4_MODEL_KEY')
    doctor.add_argument('--native-tools', action='store_true', help='Declare native tool support and include it in an explicit probe.')
    doctor.add_argument('--streaming', action='store_true')
    doctor.add_argument('--structured-output', action='store_true')
    doctor.add_argument('--usage-reporting', action='store_true')
    doctor.add_argument('--max-output-tokens', type=int, default=4096)
    doctor.add_argument('--token-parameter', choices=['max_tokens', 'max_completion_tokens'], default='max_tokens')
    doctor.add_argument('--timeout', type=float, default=60)
    probe_mode = doctor.add_mutually_exclusive_group()
    probe_mode.add_argument('--offline', action='store_true', help='No network access (the default).')
    probe_mode.add_argument('--probe', action='store_true', help='Authorize up to five small paid requests to the selected endpoint.')
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == 'doctor':
            from .adapters.openai_compatible import OpenAICompatibleProvider
            from .model_contracts import CapabilityProfile
            from .model_probe import probe
            model = ModelRef(provider='openai_compatible', name=args.model)
            profile = CapabilityProfile(model=model, native_tools=args.native_tools, streaming=args.streaming,
                                        structured_output=args.structured_output, usage_reporting=args.usage_reporting,
                                        max_output_tokens=args.max_output_tokens)
            provider = OpenAICompatibleProvider(base_url=args.base_url, profile=profile, key_env=args.key_env,
                                               token_parameter=args.token_parameter)
            if args.probe:
                report = asyncio.run(probe(provider, model, timeout=args.timeout))
                print(report.model_dump_json(indent=2))
                # Unknown usage is a limitation, not a failure of text generation.
                return 0 if all(check.passed for check in report.checks if check.capability != 'usage_reporting') else 2
            print(asyncio.run(provider.capabilities(model)).model_dump_json(indent=2))
            return 0
        policy = ShipPolicy.model_validate_json(args.policy.read_text()) if args.policy else ShipPolicy()
        base, head, files, diff, changed_lines = collect_diff(args.repo, args.base, args.head)
        review = None
        usage = UsageSummary()
        source = 'none'
        if args.review_file:
            review = parse_review(args.review_file.read_text(), files)
            source = 'fixture'
        elif args.model:
            if not args.base_url:
                raise ValueError('--model requires --base-url; no default endpoint is selected.')
            if not files:
                raise ValueError('No changes to review; no model request was made.')
            text, usage = asyncio.run(complete(
                base_url=args.base_url, model=args.model, key_env=args.key_env,
                system=SYSTEM_PROMPT, prompt=json.dumps({'changed_files': files, 'diff': diff}),
                request_id=str(uuid4()), max_output_tokens=args.max_output_tokens, timeout=args.timeout))
            review = parse_review(text, files)
            source = 'model'
        recommendation, reasons = evaluate_policy(policy, files=files, changed_lines=changed_lines,
                                                     checks=args.checks, review=review, source=source)
        report = ShipReport(base_sha=base, head_sha=head, diff_digest=text_digest(diff), policy_digest=digest(policy),
                            review_source=source, changed_files=files, changed_lines=changed_lines,
                            checks=args.checks, review=review, usage=usage,
                            model=ModelRef(provider="openai_compatible", name=args.model) if args.model else None, recommendation=recommendation, reasons=reasons)
        print(report.model_dump_json(indent=2))
        # Observe mode is never a required merge gate; eligibility is only an advisory field.
        return 0
    except ProviderFailure as exc:
        print(exc.error.model_dump_json(), file=sys.stderr)
        return 2
    except (ValueError, OSError, subprocess.SubprocessError):
        # Avoid echoing validation inputs, provider output, local paths or Git stderr.
        print(json.dumps({'error': 'INVALID_INPUT', 'message': 'Review failed. Check refs, policy/review JSON, endpoint, and diff size/type. No approval was issued.'}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
