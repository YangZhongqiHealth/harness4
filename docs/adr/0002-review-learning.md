# ADR 0002: bounded review-policy learning

Accepted for the 0.6.0a0 alpha, 2026-11-25. Scope: verifiable, reversible
learning of review checklists, integrated with the GitHub PR workflow.

## Decision

Retain immutable, content-addressed episodes and verified feedback in a private local
SQLite database. Reuse the existing state adapter's OS lock and private-file checks;
keep learning schema version 1 separate from the existing task journal schema.
Profile hashes include the fixed prompt/engine, endpoint, model revision and limits.
Only the named review-checklist section can change through the original typed
CandidatePatch contract. No original canonical contract or fixture is changed.

Keep the proposer outside authority: no tools, credentials, holdout labels or release
methods in its input. Development-only reflective search archives all proposals and
chooses one candidate. A separate trusted evaluator uses fresh paired rollouts on
one-use target/anchor groups, conservative confidence bounds and fail-closed outcomes.
This is a code/data boundary inside trusted Python, not a separate OS sandbox.

Persist the protocol and running cycle before inference, consume cohorts transactionally
before release calls, and accept only a completed evaluator receipt. Explicit operator
approval is bound to report, generation, evidence epoch and expiry. Activation updates
the pointer, approval and audit in one transaction. Rollback selects a previously active
compatible policy; feedback retraction propagates revocation through candidate ancestry.

`ship-github --learning-dir` pins the active policy, records episodes and includes its
hash in effect identity. Existing non-learning effect keys remain unchanged. Learning
and GitHub journals use separate directories. One process owns a learning store for
the full run; emergency revocation requires stopping that process first.

## Tradeoffs and rejected alternatives

Unrestricted generated Python, edits to the evaluator and automatic approval are
excluded. Self-reported success is not ground truth. Source groups are operator
attestations, not a proof of independence. Exact finding-set matching is deliberately
narrow; semantic verification remains future work. One-shot cohorts cost more data
than reusable holdouts but avoid an unimplemented adaptive-data privacy guarantee.
Per-cycle confidence does not establish a lifetime false-promotion bound.

Model weights are unchanged. Provider revision strings cannot verify the provider's
actual deployment contents. A scripted demo uses a weaker gate exclusively in demo
scope and cannot be attached to production GitHub reviews. Mocked production-gate
tests exercise the complete pipeline, not real model gains. Live qualification,
benchmark publication and multi-surface harness optimization remain future work.

Sources, formulas and rationale: [research](../research/2026-11-25-learning.md).
Operational details: [learning guide](../LEARNING.md).
