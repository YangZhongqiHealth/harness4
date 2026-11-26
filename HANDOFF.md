# Handoff

Read README.md, planning/STATUS.md, planning/RELEASE.md and ADR 0001 first.
AGENTS.md was absent from the bootstrap and remains absent.

The user's goal is a usable MIT open-source Claude Ship alternative, eventually a
higher-quality Harness 4.0. The latest requested priority is a research-informed, verifiable and reversible
learning loop. The 0.6.0a0 slice learns review guidance and connects to the existing
GitHub review → repair → approval loop;
do not claim full parity, superior accuracy or completed generic runtime issues.

`h4 ship` remains local/advisory. `h4 ship-github` is the opt-in remote coordinator.
Read docs/GITHUB_WORKFLOW.md before modifying it. Production paths are in github.py,
github_workflow.py and github_cli.py. Tests use real HTTP adapter + SQLite state,
a simulated GitHub server, and scripted model replies. No live provider call,
paid benchmark or live PR repair/approval was performed during implementation.

Policy is trusted operator input; CLI flags further narrow write grants. Repair
commits are single-parent non-force updates, confined to unique replacements in
allowed changed regular files. CI is read by exact head/name/App ID. Approval uses
a different GitHub user from the writer and PR author, with classic branch
protection required. No checkout, shell execution of PR code, merge or branch-rule
mutation occurs. CI runner isolation is the operator's responsibility.

The coordinator reuses H4-003 SQLite intents/receipts/artifacts and local locking.
Every visible write is journaled before dispatch; uncertain writes block retries.
`--reconcile` only reads GitHub evidence and persists proven receipts, without model
calls or remote writes. Absent/ambiguous evidence and policy migrations need human
inspection. GitHub has no atomic head/check/review transaction; post-write freshness
checks attempt stale-approval dismissal. Do not promise exactly-once effects.

Run `python -m pytest -q`: current suite has 288 tests (61 workflow cases and 42 learning cases).
Build a wheel and smoke `h4 ship-github --help`. CI runs Python 3.11–3.13.
Latest prior public CI: https://github.com/YangZhongqiHealth/harness4/actions/runs/45671729211
Implementation `546f230` passed Python 3.11–3.13 tests/builds:
https://github.com/YangZhongqiHealth/harness4/actions/runs/45678176491

Public repository: https://github.com/YangZhongqiHealth/harness4 (user authorized).
Main tracks origin/main. No PyPI release. Use the GitHub noreply author address.
Keep credentials out of reports/commits. Never execute PR code with write or model
credentials. Do not reset/delete the state directory to bypass pending effects.

Next product work: live qualification, App/webhook onboarding, finding verification
and quality evals, then isolated CI/feedback/conflict repair. H4-004/H4-005 generic
admission/tool services remain dependency-ready. Original TaskService.submit still
duplicates request_key; eventual admission must reject disagreement. Canonical base
contract fixtures were not changed. No independent human contract review is recorded.


## Learning handoff — 0.6.0a0

Read docs/LEARNING.md, docs/research/2026-11-25-learning.md and ADR 0002. The new
learning package implements a private SQLite evidence/candidate/release store,
no-tool reflective proposer, dev-only search, fresh paired target/anchor evaluation,
confidence bounds, explicit operator approval, transactional activation, rollback
and dependency revocation after feedback retraction. `ship-github --learning-dir`
pins the checklist and records episodes; use a different root from the write journal.

The credential-free `h4 learning demo` is permanently demo-scoped. Production runs
require --live and a budget/protocol, verified labels and independent source groups.
The 202-case integration uses HTTP mocks, not a paid model or live benchmark. No
superiority claim is justified. Existing canonical contract fixtures are unchanged.
Keep generated policies away from permission/evaluator/code surfaces. The local OS
owner is trusted; the lock prevents concurrent use, including emergency retraction
until the current coordinator stops. Fresh release cohorts are mandatory each cycle.
