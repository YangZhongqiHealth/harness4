"""CLI wiring kept separate from local review and the pure coordinator."""
import json
from uuid import uuid4

from .adapters.sqlite_state import SQLiteState, StoreFailure
from .contracts import digest
from .github import GitHub, GitHubFailure
from .github_workflow import GitHubPolicy, WorkflowJournal, run_workflow
from .model_contracts import strict_object
from .provider import complete


async def execute(args):
    policy = GitHubPolicy.model_validate_json(json.dumps(strict_object(args.policy.read_text())))
    calls = []

    async def model(system, payload):
        text, usage = await complete(base_url=args.base_url, model=args.model, key_env=args.key_env,
                                     system=system, prompt=json.dumps(payload), request_id=str(uuid4()),
                                     max_output_tokens=args.max_output_tokens, timeout=args.timeout)
        calls.append({'model': args.model, 'usage': usage.model_dump(mode='json')})
        return text

    try:
        with SQLiteState(args.state_dir) as state:
            journal = WorkflowJournal(state, policy, args.pr)
            try:
                report = await run_workflow(GitHub(policy.repository, key_env=args.github_key_env),
                    policy, args.pr, model, journal, write=args.write, approve=args.approve,
                    approver=GitHub(policy.repository, key_env=args.approval_key_env) if args.approve else None,
                    check_polls=args.check_polls, poll_seconds=args.poll_seconds, reconcile=args.reconcile)
                report['model_calls'] = calls
                report['policy_digest'] = digest(policy)
                artifact = await state.put_artifact(policy.repository, json.dumps(report).encode(), 'application/json')
                report['artifact'] = artifact.model_dump(mode='json')
                return report
            finally:
                await journal.close()
    except GitHubFailure as exc:
        return {'status': 'blocked', 'reason': str(exc), 'model_calls': calls}
    except StoreFailure as exc:
        return {'status': 'blocked', 'error': exc.error.model_dump(mode='json'), 'model_calls': calls}
    except (KeyError, TypeError, IndexError):
        return {'status': 'blocked', 'reason': 'Malformed GitHub evidence; no further action taken.', 'model_calls': calls}
