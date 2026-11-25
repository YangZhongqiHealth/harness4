# Handoff

Read README.md, planning/STATUS.md, planning/RELEASE.md and ADR 0001 first.
The user's clarified goal is a usable MIT-licensed open-source alternative for the
PR review/fix/approval workflow described by Claude Ship. The first alpha implements
local read-only review plus observe-mode policies. Do not describe it as feature
parity, an automatic approval system, or a proven accuracy improvement.

`h4 ship` accepts Git base/head refs, optional trusted policy, operator-supplied CI
status, and either an offline review fixture or explicit model + endpoint. It emits
commit-pinned JSON with usage and model identity. Fixtures never qualify as eligible.
See tests/test_ship.py for provider, Git, policy and CLI regression coverage.

H4-001 and the H4-002 model gateway are implemented. Native tools, structured
output, streaming, fake provider and explicit probes are covered by offline tests;
live endpoint qualification is still pending. H4-003 local persistence is now implemented; H4-004 and H4-005 are dependency-ready.
The user's release direction permits a narrow product slice without pretending the
original dependency backlog is complete. Implement subsequent work in reviewable
increments with tests and truthful status updates.

Run `python -m pytest -q` (183 passed locally). No live provider test was performed.
Do not execute PR-controlled code with credentials. Keep source control policy and
CI evidence in trusted contexts. Automatic repair, approvals and merging need their
own authorization, freshness checks, isolation and negative tests.

AGENTS.md was absent from the bootstrap. No independent human contract review is
recorded. Original TaskService.submit still duplicates request_key; future admission
must reject disagreement. Original canonical schema fixtures remain unchanged.

Public repository: https://github.com/YangZhongqiHealth/harness4
Implementation commit `6bbb60d` passed GitHub CI on Python 3.11–3.13.
The local main branch tracks origin/main. No PyPI release has been made.

Gateway SDK docs: docs/PROVIDERS.md. Full product gates: planning/PRODUCT.md.
`h4 doctor` defaults to offline; only --probe authorizes paid requests. Model stream
text is provisional; only a validated final response can expose proposed tool calls.
No tool execution or grants were added. Complete H4-004 trusted admission and H4-005 local tool authority next.

Persistence semantics: docs/PERSISTENCE.md; example: examples/durable_task.py.
Recover pending intents before issuing effects. Persist result receipts before
reduction. Current OS lock and fences are local, not distributed timed leases.
