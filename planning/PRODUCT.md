# Complete PR lifecycle and Harness 4.0 acceptance plan

The product goal is a usable, model-portable, self-hostable open-source alternative
covering PR review, repair and policy decisions, with evidence-based improvement.
A public alpha is the starting point. Completion and superiority are separate claims.

Reference workflow: https://claude.com/resources/articles/introducing-claude-ship

## Delivery gates

| Stage | User capability | Required evidence before claiming completion |
|---|---|---|
| Model gateway | Choose a provider; reproducibly inspect capabilities | Offline conformance plus opt-in real endpoint matrix; unsupported features explicit |
| Durable runtime | Resume review/repair after interruption without duplicate writes | SQLite state/event atomicity, idempotency, scoped lookups, crash/restart tests, conservative unknown usage |
| Review and verification | Receive actionable findings tied to the exact PR revision | Full relevant context, independent finding verification, location validation, prompt-injection cases, benchmark precision/recall |
| Isolated repair | Generate a fix, execute bounded tests and inspect the resulting diff | Credentials separated from untrusted code, sandbox escape negatives, network policy, budget/time bounds, cancellation, no unrelated edits |
| PR steward | Address failing checks, feedback and conflicts across pushes | GitHub head freshness, durable event deduplication, deterministic recovery, explicit write grants and undo receipts |
| Policy decisions | Apply trusted team rules to current review/test evidence | Base-branch policy provenance, authenticated evidence, required checks/branch rules, stale-head rejection, human escalation, auditable decisions |
| Harness 4.0 learning | Propose and evaluate better scoped policies over future work | Immutable evidence, separate dev/held-out sets, evaluator isolation, no hidden labels, regression gates, human-approved promotion and rollback |
| Community release | Install, configure and operate without maintainer help | Fresh-machine quickstart, examples, CI, docs, contributor workflow, security reporting, reproducible releases |

H4-001–025 remain the dependency backlog. Complete capabilities in increments; do
not mark original issues done merely because a narrow PR command exists. Provider
and local state implementations are complete; trusted admission and tool authority
are next. Native
API adapters, GitHub App installation, webhooks and operator UI are separate work,
not implied by a compatible endpoint adapter or CLI.

## How an upgrade claim will be tested

Publish benchmark inputs, public ground truth, exact versions/configurations, model
and token budgets, outcomes and failure cases. Measure useful findings versus false
positives, successful independently tested repairs, regressions, time to completion,
cost per accepted fix, recovery failures and unauthorized-action rate. Compare under
equivalent model access and budget where possible, and disclose non-equivalent setups.

For learning, compare frozen baseline versus candidate on unseen cases with anchor
regressions and explicit uncertainty. A fake demo proves lifecycle mechanics only.
Do not advertise better accuracy, safety or learning from architecture diagrams,
unit-test counts or a few selected examples. Self-hosting and model choice can be
claimed when implemented; quality improvements require measurements.

## Current boundaries

The local `ship` command remains advisory. The 0.5.0a0 `ship-github` slice implements
opt-in review posting, restricted repair commits, fresh CI reads and policy-gated
approval with durable intents and explicit evidence reconciliation. It has offline
HTTP/SQLite lifecycle tests; live model/GitHub qualification remains pending.

It does not execute PR code locally or merge. Only same-repository text PRs and
classic branch protection are supported. Separate same-model review calls do not
establish independent verification or higher accuracy. CI failures/conflicts/human
feedback escalate rather than being repaired automatically. App onboarding, webhooks,
distributed execution and general admission/tool services remain unfinished.
The 0.6.0a0 review-learning slice now implements evidence intake, bounded reflective
search, a one-use independent release cohort, operator-approved activation, rollback
and evidence retraction. Its evaluator boundary is logical within a trusted local
coordinator. General multi-surface evolution and measured live gains remain pending.
See docs/LEARNING.md and the research report for scope and statistical assumptions.
See docs/GITHUB_WORKFLOW.md for the exact implemented boundary.
