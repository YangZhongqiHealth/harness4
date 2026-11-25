# GitHub implementation backlog

## [H4-001] Ratify shared contracts and ADR (M0)

### Objective
Review starter types against RFC; freeze P0 task/result/event/patch and error schemas; generate JSON Schema fixtures.

### Dependencies
None

### Scope
contracts, ports, schema fixtures

### Specification
`docs/specs/00-contracts.md` and `docs/DESIGN.md`.

### Acceptance tests
Round-trip valid records; reject internal authority fields, stale transitions, incompatible versions; import-boundary test.

### Prohibited shortcuts
Do not silently widen permissions or mark incomplete interfaces implemented.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-002] Implement fake and OpenAI-compatible providers (M0)

### Objective
Fake scripted responses; direct compatible adapter; normalized usage and errors; capability probes.

### Dependencies
H4-001

### Scope
providers, config

### Specification
`docs/specs/01-product-and-provider.md` and `docs/DESIGN.md`.

### Acceptance tests
Native tool roundtrip, text-only fallback, malformed streaming fragments, rate-limit and unknown usage fixtures.

### Prohibited shortcuts
No implicit endpoint fallback or secret logging.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-003] Implement SQLite and artifact repositories (M0)

### Objective
Migrations; transaction-scoped task/step/event/operation stores; scoped queries; artifact digests.

### Dependencies
H4-001

### Scope
state, storage

### Specification
`docs/specs/02-runtime-and-state.md` and `docs/DESIGN.md`.

### Acceptance tests
Duplicate key conflict; state/event atomicity; restart persistence; orphan cleanup.

### Prohibited shortcuts
No network inside transaction or unscoped resource lookup.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-004] Implement admission and policy pinning (M0)

### Objective
Default agent; request key fingerprint; trusted effective policy and grant resolution.

### Dependencies
H4-001, H4-003

### Scope
application, policy, kernel

### Specification
`docs/specs/00-contracts.md` and `docs/DESIGN.md`.

### Acceptance tests
Same request returns same ID; different payload conflicts; new policy does not change old task.

### Prohibited shortcuts
Client cannot set active policy or grant itself access.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-005] Implement local tool boundary (M0)

### Objective
Read mounted files and create private artifacts with explicit grants and stable intent IDs.

### Dependencies
H4-001, H4-003

### Scope
tools, security, environment

### Specification
`docs/specs/04-tools-and-environment.md` and `docs/DESIGN.md`.

### Acceptance tests
Traversal, symlink, oversized file and revoked-grant negatives; idempotent local receipt.

### Prohibited shortcuts
No unrestricted shell, network or broad host filesystem access.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-006] Implement context compiler and manifest (M0)

### Objective
Required context and tool schema assembly; token budget; source IDs and omissions.

### Dependencies
H4-001, H4-002, H4-004

### Scope
execution, context

### Specification
`docs/specs/03-context-memory-skills.md` and `docs/DESIGN.md`.

### Acceptance tests
Required content never silently truncated; paired tool results retained; manifest pinned.

### Prohibited shortcuts
Do not store hidden reasoning or unauthorized content.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-007] Implement bounded actor and reducer (M0)

### Objective
Deterministic next-command reducer; model/tool reservations; persist results; complete/fail/cancel.

### Dependencies
H4-002, H4-003, H4-004, H4-005, H4-006

### Scope
kernel, execution

### Specification
`docs/specs/02-runtime-and-state.md` and `docs/DESIGN.md`.

### Acceptance tests
Fake full task; bounded turns; crash after receipt consumes result; malformed actions rejected.

### Prohibited shortcuts
Model cannot directly execute effects; no infinite loop.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-008] Implement init, doctor, chat, run and inspect (M0)

### Objective
Single service layer; API-key reference; stream output; TaskResult and --json.

### Dependencies
H4-002, H4-004, H4-007

### Scope
application, cli

### Specification
`docs/specs/01-product-and-provider.md` and `docs/DESIGN.md`.

### Acceptance tests
Credential-free quickstart; opt-in live probe; persisted inspect; text-only chat; no key in logs.

### Prohibited shortcuts
Do not pretend daemon/background tasks continue when process exits.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-009] M0 integration and threat smoke suite (M0)

### Objective
Clean install, default assistant, safe artifact, one-endpoint opt-in live smoke.

### Dependencies
H4-005, H4-007, H4-008

### Scope
tests, packaging

### Specification
`docs/specs/07-integration-and-benchmarks.md` and `docs/DESIGN.md`.

### Acceptance tests
Restart, refusal, cancellation, budget limit, credential canary and invalid action tested.

### Prohibited shortcuts
No live charges in default CI.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-010] Capture feedback and evidence projections (M1)

### Objective
Bind correction/outcome to task/artifact/policy; redacted episode and consent.

### Dependencies
H4-003, H4-007, H4-008

### Scope
feedback, evidence

### Specification
`docs/specs/05-evidence-and-learning.md` and `docs/DESIGN.md`.

### Acceptance tests
Duplicate feedback idempotent; stale artifact rejected; unverified outcome not objective label.

### Prohibited shortcuts
Never fabricate labels from reflection.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-011] Implement dataset manifests and normalization fixture (M1)

### Objective
Grouped train/dev/target/anchor fixtures; deterministic expected values; sealed split boundary.

### Dependencies
H4-010

### Scope
evaluation, recipes

### Specification
`docs/specs/06-evaluation-and-release.md` and `docs/DESIGN.md`.

### Acceptance tests
Disjoint groups; zero/null/empty-string anchors; expected answers not in actor context.

### Prohibited shortcuts
Fake model behavior labeled scripted, not proof of real improvement.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-012] Implement immutable candidates and text patches (M1)

### Objective
Validate section allowlist, scope, base/component hash; immutable archive and evidence references.

### Dependencies
H4-004, H4-010

### Scope
policy, learning

### Specification
`docs/specs/05-evidence-and-learning.md` and `docs/DESIGN.md`.

### Acceptance tests
Reject stale/no-op/forbidden patch; preserve unrelated section; candidate not visible before activation.

### Prohibited shortcuts
No arbitrary code generation or evaluation/security mutation.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-013] Implement paired dev and sealed evaluation (M1)

### Objective
Clone per rollout; same model/grants/budgets; trusted protocol and per-case results.

### Dependencies
H4-007, H4-011, H4-012

### Scope
evaluation

### Specification
`docs/specs/06-evaluation-and-release.md` and `docs/DESIGN.md`.

### Acceptance tests
Missing/duplicate cases, anchor regressions, split leakage and hard violations block eligibility.

### Prohibited shortcuts
Never let optimizer read sealed labels or retry until pass.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-014] Implement reflection optimizer and cycle coordinator (M1)

### Objective
Structured hypothesis and bounded patches; dev-only selection; one sealed submission; separate budget.

### Dependencies
H4-010, H4-011, H4-012, H4-013

### Scope
learning

### Specification
`docs/specs/05-evidence-and-learning.md` and `docs/DESIGN.md`.

### Acceptance tests
Insufficient evidence abstains; malformed patches rejected; budget exhaustion no promotion.

### Prohibited shortcuts
No release activation access or live side effects.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-015] Implement approval, CAS promotion and rollback (M1)

### Objective
Verify trusted report and approval bindings; atomic pointer/audit event; scope and compatibility check.

### Dependencies
H4-003, H4-012, H4-013

### Scope
release, policy

### Specification
`docs/specs/06-evaluation-and-release.md` and `docs/DESIGN.md`.

### Acceptance tests
Stale/expired/replayed approval rejected; fake report never production; new task pins new version; rollback restart.

### Prohibited shortcuts
Approval cannot bypass hard gate; rollback does not undo external effects.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-016] Ship deterministic and live learning demos (M1)

### Objective
Fake lifecycle and opt-in paid live mode; reports, diff, user approval, new task and rollback.

### Dependencies
H4-009, H4-014, H4-015

### Scope
cli, recipes, tests

### Specification
`docs/specs/07-integration-and-benchmarks.md` and `docs/DESIGN.md`.

### Acceptance tests
Fake unseen fixture gain + harmful candidate rejection + no feedback abstention; live reports failures honestly.

### Prohibited shortcuts
Do not claim SOTA or live learning gain from fake adapter.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-017] Implement durable inbox, scheduler and wait/resume (M2)

### Objective
Signed ingress, dedup, leases, matching predicates, timers, root causality and task locks.

### Dependencies
H4-007, H4-016

### Scope
runtime, state

### Specification
`docs/specs/02-runtime-and-state.md` and `docs/DESIGN.md`.

### Acceptance tests
Wake-before-wait, duplicate delivery, expired worker, restart, idle inference zero.

### Prohibited shortcuts
No blind re-execution of uncertain writes.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-018] Implement HTTP and reconnectable events (M2)

### Objective
Authenticated loopback API; submit/status/cancel/feedback/events; cursor reconnect.

### Dependencies
H4-008, H4-017

### Scope
server, application

### Specification
`docs/specs/01-product-and-provider.md` and `docs/DESIGN.md`.

### Acceptance tests
Scope checks, request idempotency, replay gap and unauthorized access tests.

### Prohibited shortcuts
No unauthenticated remote bind.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-019] Implement operation reconciliation and approval broker (M2)

### Objective
Typed approval binding, operation ledger, fenced dispatch, unknown-effect state.

### Dependencies
H4-005, H4-017

### Scope
tools, kernel, security

### Specification
`docs/specs/04-tools-and-environment.md` and `docs/DESIGN.md`.

### Acceptance tests
Crash at each boundary, one-use approval, external version conflict, ambiguous effect reporting.

### Prohibited shortcuts
No exactly-once claim for unsupported remote APIs.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-020] Fault injection, isolation and budget suite (M2)

### Objective
Hierarchical reservations, process boundaries, causal loop caps, recovery tests.

### Dependencies
H4-017, H4-018, H4-019

### Scope
tests, security

### Specification
`docs/specs/02-runtime-and-state.md` and `docs/DESIGN.md`.

### Acceptance tests
Concurrent reservation limits, compromised worker attempts, stale lease, cancellation, secret canaries.

### Prohibited shortcuts
No unrestricted code execution or learner credentials.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-021] GitHub read-only review recipe (M3)

### Objective
Signed event or fixture, immutable head snapshot, structured verified findings and feedback.

### Dependencies
H4-020

### Scope
recipes, adapters

### Specification
`docs/specs/04-tools-and-environment.md` and `docs/DESIGN.md`.

### Acceptance tests
Stale SHA detected, no duplicate event, read-only scope, seeded bugs scored.

### Prohibited shortcuts
No automated merge or comment writes by default.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-022] Second domain and plugin conformance (M3)

### Objective
Document action-item extraction with deterministic fields and user correction; plugin interface.

### Dependencies
H4-016, H4-020

### Scope
recipes, plugins

### Specification
`docs/specs/07-integration-and-benchmarks.md` and `docs/DESIGN.md`.

### Acceptance tests
Same runtime and learning contracts with different evaluator; setup guide.

### Prohibited shortcuts
Do not fork core agent loop per domain.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-023] Integrate optional GEPA optimizer (M4)

### Objective
License/revision audit; adapter to typed patches and dev-only scoring; fallback.

### Dependencies
H4-014, H4-016

### Scope
learning, adapters

### Specification
`docs/specs/05-evidence-and-learning.md` and `docs/DESIGN.md`.

### Acceptance tests
Same evaluation budget; no sealed access; archive and reproducible results.

### Prohibited shortcuts
No dependence on a separate paid model.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-024] Scoped interventions and learning ROI research (M4)

### Objective
Component attribution hypotheses, scope overlays, retention anchors, value-based scheduler.

### Dependencies
H4-016, H4-022, H4-023

### Scope
context, memory, learning

### Specification
`docs/specs/03-context-memory-skills.md` and `docs/DESIGN.md`.

### Acceptance tests
Matched-budget ablation; negative transfer tests; unsupported case abstains.

### Prohibited shortcuts
Correlation does not establish causal credit; no automatic paid learning.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.

---

## [H4-025] Reproducible benchmark and release report (M4)

### Objective
Compare B0–B5; grouped split, cost accounting, uncertainty and negative results.

### Dependencies
H4-021, H4-022, H4-023, H4-024

### Scope
benchmarks, docs

### Specification
`docs/specs/07-integration-and-benchmarks.md` and `docs/DESIGN.md`.

### Acceptance tests
Pinned model/config, reproducible fixtures, matched constraints, transparent failures.

### Prohibited shortcuts
No SOTA marketing without empirical superiority for defined conditions.

### Definition of done
Implement the scoped behavior, add automated tests, document actual user-visible behavior/errors, run relevant CI, and note unsupported features. No unrelated public-contract changes without reviewed ADR.
