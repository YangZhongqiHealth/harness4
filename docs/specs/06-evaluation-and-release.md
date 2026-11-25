# SPEC-06 — Independent evaluation, promotion and rollback

Master RFC §14, §19. Depends SPEC-00/02/04/05. Critical trusted boundary. M1 deterministic demo only; live evidence protocol must be explicit and powered. No general-purpose automatic reward.

## Evaluation protocol

`EvalCase`: input artifact, family/group, fixture version, allowed tools, seed, expected output held by evaluator. `EvalProtocol`: immutable ID/digest; evaluator code/version, data manifest, model/profile, limits, primary metric, target gain, anchor noninferiority, hard checks, sample plan and cost cap. `Scorecard`: candidate and incumbent digests, protocol/data hash, paired outcomes, missing/failed cases, target and anchor metrics, uncertainty, usage, violations and trusted runner identity. Actor never sees expected answers. Baseline and candidate isolated environments, same task inputs, frozen knowledge, model/config and budgets; randomize ordering for subjective evaluations. Record tool results as evidence; do not use replayed answers to score new actions. LLM judge can supply provisional feedback, not alone authorize consequential changes. Missing cases are not dropped to inflate scores.

## P0 deterministic fixture gate

Local table-normalization tasks preserve missing values and field semantics. Build seeded groups: development examples, unseen target fixtures from distinct groups, unrelated anchors (e.g., zero and empty string preservation). Fake model is scripted to fail known rule under baseline and correct it with patch; this validates plumbing only. Predeclare exact thresholds: all required cases completed, target set nonempty, anchor set nonempty, target exact-match count improves by at least 1, anchor count does not decrease, no hard violations, budget met. Fixture gate limited to demo scope, not production release. Real endpoint demo records results even when no candidate passes. For live promotion require predeclared live protocol and independent evidence; no fall back to fake fixture gate.

## Live evaluation design

Use paired case-level differences. Binary exact-match: report discordant counts, paired difference and uncertainty; choose exact test or grouped bootstrap under predeclared assumptions. Cluster by independent source, not seeds; repetitions estimate variability. Predeclare minimum practically meaningful improvement, confidence method, power/sample plan, quality noninferiority and anchor thresholds, cost constraints. Selection on dev only, sealed comparison once per protocol/candidate cycle; no retry-until-pass. If insufficient evidence, missing labels, changed endpoint/version, or ambiguous effects -> inconclusive. Safety violations deterministic rejection. Independent reviewer context is useful but same model may correlate errors. P1/P2 canary only low-risk authorized traffic, no duplicated external writes, monitor outcome drift and delayed labels, freeze/rollback on incident.

## Release transaction

States proposed -> validated -> dev_evaluated -> sealed_evaluated -> eligible/rejected/inconclusive -> approved -> active (optional canary later) -> retired/rolled_back. Gate verifies signed or authenticated report from trusted runner, exact base/candidate/protocol/data/profile/scope, evidence class, expiry, live security epoch and operator approval. Atomic CAS of active pointer + audit event. A valid prior scorecard alone not authorization; changed incumbent -> stale, re-evaluate. Approval cannot override rejection, and eligibility is not approval. Demo policies stored under dedicated scope. One-time token bound to release hash; no raw token in learner. Rollback verifies target compatibility/security, records actor and reason, switches pointer only for new tasks. Running revoked-policy tasks stopped/replanned as required. No undo of external effects; separately authorize compensation.

## Acceptance

Test candidate swapping after approval, stale base, expired/replayed approval, unknown evaluator, empty/overlapping dataset, missing target/anchor cases, incomplete rollout, fake report for live scope, budget exceed, failed hard checks, concurrent promotion CAS, activation across restart and rollback with old tasks still pinned. Trusted repository integration tests must prove learner cannot invoke activation. Pure contract gate in starter tests deterministic decision math only; authentication, transaction, evidence completeness and isolation still require implementation.
