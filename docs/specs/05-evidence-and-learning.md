# SPEC-05 — Evidence, feedback and policy optimization

Master RFC §§11–13. Depends SPEC-00/02/03 and trusted evaluator interface SPEC-06. Reference: reflection optimization, GEPA, ACE, Hermit, AutoSaddler and Meta-Harness as listed in RFC. M1 uses bounded text-section changes; P2 external optimizer adapters are research tracks, not dependencies.

## Evidence lifecycle

Committed task result + context manifest + observations + verified outcome -> sanitized episode -> feedback validation -> eligibility + family/group assignment -> dataset snapshot. Feedback contains task/artifact/policy hash, source identity, rubric/validator version, value, timestamp, consent and verification status. Distinguish user correction, deterministic test, environment outcome, rating, LLM judgment and reflection. No rating silently converted into ground truth. Unverified experience may support hypothesis generation, not objective performance claims. Validate outcome against original artifact revision. Delayed labels append; corrections supersede; deletion invalidates dependent snapshots/candidates. Separate raw telemetry from learner view. Data partition by source group/project/time BEFORE selection, never random rows from same source trajectory across splits. Training/dev accessible to optimizer; sealed inputs/labels not accessible, except input passed to isolated rollout actor. Release evaluator outputs permitted aggregate statistics only. Reused holdout cannot be treated as fresh; require new disjoint cohort or approved statistical protocol.

## Policy representation and optimizer port

Immutable bundle of named sections + compatibility metadata; actor loads pinned content, not optimizer outputs. Candidate patch has exact parent hash, scope, section and expected old text digest, replacement text, evidence IDs, hypothesis, optimizer version. P0 only replace existing named sections. No authority, evaluator, shell, credentials, budget limit or tool registry change. Validate paths/types, bounded length, scope/evidence eligibility and base/component digests. Even text can be malicious; tool boundary remains enforced. Store canonical hash, archive rejected and no-op patches. Learner identity can stage only; no active pointer access.

```python
class Optimizer(Protocol):
    async def propose(self, incumbent, evidence, archive, search_space, budget):
        # yields typed patches; never calls production tools or release API
        ...
```

## M1 learning algorithm

1. User explicitly requests learning and approves budget. Freeze incumbent and eligible dataset manifest, verify sufficient target cases and anchors. If absent return INSUFFICIENT_EVIDENCE with remediation; no model call required.
2. Cluster recurring failure signatures (e.g., incorrect null normalization). Choose hypothesis based on verified examples and counterexamples. Sanitize and restrict evidence to intended scope. Ask same configured LLM for typed patch via schema; invalid output bounded repair then reject.
3. Validate patch and stage candidate immutable. Evaluate incumbent and candidate with fresh cloned dev environments, same provider/config/grants/budgets, no learning in rollouts. Record per-case quality, usage, errors and latency. Keep unsuccessful candidates; never erase failed attempts.
4. Select at most one candidate per cycle by preregistered dev rule (highest target exact match, tie: lower cost then stable hash). Sealed runner owns test cases; no iterative optimization based on sealed results. If budget depleted, incomplete -> no activation.
5. Send report to independent release gate. Learner returns proposal/abstention; cannot activate. User approves eligible candidate. Next tasks pin new policy; rollback restores pointer. Running tasks stay pinned, except security revocation.

Fast learning: explicit user preferences and facts with consent; inferred lesson as proposal. Slow learning: cross-task evaluated behavioral changes. Neither mode permits unlimited inference or scope widening. Default ordinary chat may record only authorized feedback, not run paid optimizer automatically. API-only user can test local fixtures, but unstructured tasks may remain inconclusive.

## P2 research directions (not M1)

Typed interventions compare component changes on paired dev groups with matched evaluation budgets. Record causal trace lineage and component hashes; diagnose hypotheses, not causal proof from correlation. Test interaction effects with small factorial experiments only if budget justifies. Add GEPA adapter for textual optimization after fixture conformance; compare reflection vs GEPA vs memory-only vs frozen policy. Scope resolution avoids negative transfer; use target and retention anchors. Learning ROI scheduler estimates recurring volume, conservative benefit, cost and risk; no automatic paid learning until opt-in. A code-level optimizer operates only in isolated offline sandbox, with reviewed software releases; never writes trusted runtime.

## Acceptance

No labels -> no proposal activation; corrupt/missing artifact -> reject feedback; duplicate feedback idempotent; no-op or stale patch rejected; secret canary absent from learner; held-out expected outputs never appear in model input; harmful candidate fails anchors; candidate with only self-reported success ineligible. Archive supports replay of known evaluation results, not fake re-execution of novel actions. Report cost and skipped cases; no SOTA claim without matched benchmark evidence.
