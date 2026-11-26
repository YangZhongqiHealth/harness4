# Implementation status

Updated 2026-11-25. Public MIT-licensed alpha:
https://github.com/YangZhongqiHealth/harness4

| Work | Status | Evidence |
|---|---|---|
| H4-001 | Contract implementation complete; independent review not recorded | Typed records, scoped Protocols, JSON Schema and wire fixtures |
| Local PR workflow | Implemented | `h4 ship`, commit-pinned reports, observe policy, fixture mode and model review |
| H4-002 | Implementation complete; live endpoint qualification pending | Model port, compatible/fake adapters, tools, structured output, SSE and probes |
| H4-003 | Implementation complete | SQLite transactions, idempotency, local fences, receipts/results, private artifacts and crash tests |
| GitHub lifecycle slice | Implemented in 0.5.0a0; live qualification pending | `ship-github`: real REST adapter, review posting, bounded repair commits, repeat review, authenticated CI reads, policy-gated approval and durable reconciliation |
| Review learning slice | Implemented in 0.6.0a0; live gains unmeasured | Verified feedback, bounded reflective search, one-use release cohorts, confidence/retention gates, explicit activation, rollback and retraction; integrated with GitHub reviews |
| H4-004, H4-005 | General runtime implementations remain dependency-ready | GitHub slice has a narrow operator-policy/write boundary; it does not complete the generic admission service or tool broker |
| H4-006–025 | Not implemented as general runtime capabilities | Follow original dependency graph; do not infer completion from the GitHub product slice |
| Open-source packaging | Published repository; no PyPI release | MIT, contribution/security docs, CI and package smoke checks |

Current local validation: `python -m pytest -q` — 289 tests, including 61 GitHub
workflow cases and 43 learning cases. The GitHub tests use httpx MockTransport, scripted model responses,
and real SQLite storage. They exercise review → repair → new-head review → CI →
approval, restart deduplication, read-only reconciliation, stale head/base/CI,
separate principals, protected paths, symlinks, response/pagination limits and CLI
reports. They do not establish live API/model compatibility or review accuracy.

Previous public CI: Python 3.11–3.13 passed at `373e617` (185 tests):
https://github.com/YangZhongqiHealth/harness4/actions/runs/45671729211
The 0.5.0a0 implementation `546f230` passed GitHub CI on Python 3.11–3.13:
https://github.com/YangZhongqiHealth/harness4/actions/runs/45678176491

`ship-github` defaults to observation. Actual posting/repair requires `--write` and
repair policy grants; approval additionally requires `--approve`, policy permission,
a separate user token and classic branch protection. CI is read from GitHub for the
exact reviewed head and expected App. No PR code runs in the coordinator. Testing
runs in separately configured CI. No merge endpoint is called.

Remaining product gaps: live-provider/PR qualification, GitHub App installation and
webhooks, fork support, full dependency context and independent finding verification,
isolated local execution, CI-log diagnosis, conflict/feedback repair, distributed
coordination, provider-enforced monetary budgets and measured quality/learning gains. This is not full
Claude Ship parity or a demonstrated generation-ahead system.

See docs/GITHUB_WORKFLOW.md for deployment, limits and recovery;
planning/PRODUCT.md remains the full acceptance plan.

The 0.5.0a0 wheel built offline and was installed into a separate smoke environment.
The installed `ship-github --help` and all 61 GitHub integration tests passed from
outside the source checkout, with repository pytest configuration disabled.


The 0.6.0a0 learning tests exercise immutable evidence, development-only proposals,
release confidence bounds, one-use cohorts, real process-crash recovery, approval
expiry/replay/ABA prevention, transactional failure rollback and evidence retraction.
A 202-case HTTP-mocked integration executes 809 model requests through the real
adapter, passes the production gate, activates a checklist, uses it in the GitHub
CLI, rolls back and checks persisted effect deduplication. All data and responses
in this test are synthetic; it is not a performance measurement.

Read docs/LEARNING.md, docs/adr/0002-review-learning.md and the dated research report.
The local OS owner is trusted. Proposer isolation is logical, not an OS sandbox.
General learning surfaces and live qualification remain pending; do not mark all
H4-011–015 capabilities complete. No paid inference was run for this increment.

The 0.6.0a0 wheel builds offline; installed CLI help and the full learning demo pass
outside the checkout. Installed learning/GitHub integration tests pass independently
of repository pytest configuration. Public CI evidence is recorded after publication.


Public CI for the learning implementation `7dfcdac` passed on Python 3.11–3.13
(288 tests, installed CLI/demo checks and package builds):
https://github.com/YangZhongqiHealth/harness4/actions/runs/45736444624
The subsequent lineage guard adds one regression test (289 locally): a proposer
cannot turn a previously active baseline into a feedback-dependent candidate.

README positioning review (2026-11-26): the landing page now leads with the
open-source Claude Ship alternative and verifiable checklist-learning lifecycle.
Added adoption modes, a worked learning example and a clear current/next capability
matrix. Repository naming and implementation scope are unchanged. Validation:
289 tests passed; installed demo output, local links and section anchors checked.
