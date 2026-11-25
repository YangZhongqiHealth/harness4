# Implementation sequence and merge gates

| Milestone | Dependencies / issue range | Deliverable |
|---|---|---|
| M0 | H4-001–009 | One-key bounded assistant, persisted outputs, safe local tools |
| M1 | H4-010–016 | Evidence-driven scoped learning, isolated demo, promotion and rollback |
| M2 | H4-017–020 | Durable event scheduler, waits, reconciliation, security tests |
| M3 | H4-021–022 | GitHub read-only integration, second-domain portability |
| M4 | H4-023–025 | Optional optimizer adapters, scoped interventions, benchmark |

Start with H4-001 (ratify contracts and ADR), then implement provider and persistence in parallel, followed by kernel and tool boundary. Application and context work may begin against fake ports once contracts ratified. Do not merge a PR that invents incompatible schemas. M0 needs basic persistence, permission and budget before any live tools. M1 needs evaluator isolation before learner activation, not after. M2 adds distributed-style fencing semantics without requiring distributed deployment. M4 research claims gated by experiments.

Each issue is a small reviewable increment, with dependencies, test requirements, and prohibited shortcuts. `issues.json` is machine-readable; `ISSUES.md` includes templates. Merge order follows dependency DAG, not numeric order alone. Suggested branch `h4/<issue-id>-<slug>`. Coding agent prompt: implement one issue only, read linked specs + master RFC, run acceptance tests, list actual changes and remaining blockers; do not claim unimplemented features. Update contracts only with reviewed ADR. No external repo changes have been made.
