# Public alpha release plan

The user's 2026-11-24 product direction is a usable MIT-licensed open-source
alternative for Claude Ship's PR workflow. This supersedes the bootstrap's one-issue
limit for this release increment. Original H4 dependency issues remain tracked; a
narrow PR review slice does not mark unrelated runtime issues complete.

## Implemented first slice

- Installable `h4 ship` CLI: pinned local Git diff, offline policy check, optional
  text-only model review, structured report, usage and model identity.
- Trusted observe policy, protected paths, change-size limit, explicit CI evidence.
- MIT, contribution/security docs, Python CI and a safe offline Actions example.

## Publication completed — 2026-11-24

- Public repository: https://github.com/YangZhongqiHealth/harness4
- MIT license, source and documentation verified remotely.
- 83 tests passed locally; wheel installation and end-to-end CLI smoke passed.
- GitHub CI passed tests and builds on Python 3.11–3.13 for `6bbb60d`.
- Commit author uses the GitHub noreply address.
- This is an alpha repository publication; no PyPI package has been released.

## GitHub lifecycle increment — 0.5.0a0, 2026-11-25

The requested review → repair → approval slice now has a usable CLI and real GitHub
REST adapter, operator policy, durable write intents, CI evidence, two review passes,
bounded repair commits and separate-user approvals. Sixty-one new tests cover the loop,
negative cases and evidence-only recovery. Deployment instructions and a safe-default
policy are in docs/GITHUB_WORKFLOW.md and examples/github-policy.json.

This is not a live-qualified release or full product parity. No real provider call
or real PR repair/approval has been performed. GitHub App/webhook onboarding, fork
PRs, CI-failure/conflict repair, human-feedback handling, richer verification and
quality/learning benchmarks remain milestones. No merge or production-security claim.
