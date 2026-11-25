# SPEC-07 — Vertical slices, end-to-end interaction and research validation

Master RFC §§15–22. All preceding contracts required. Milestone acceptance is based on real observed behavior, not existence of class names.

## Sequence A: one-key interactive task

```mermaid
sequenceDiagram
 participant U as CLI / User
 participant A as Application
 participant K as Kernel + State
 participant C as Context
 participant M as Model adapter
 participant T as Tool gateway
 U->>A: goal + request key
 A->>K: admit; pin policy and grant refs
 K->>C: compile snapshot
 C-->>K: request + manifest
 K->>M: reserved inference
 M-->>K: normalized response
 K->>T: validated action + stable operation ID
 T-->>K: authorized receipt
 K->>K: commit and reduce until done
 K-->>A: final TaskResult + events
 A-->>U: answer, artifacts, verification state
 U->>A: correction linked to artifact
 A->>K: persist feedback
```

## Sequence B: learning cycle

User starts explicit budgeted learning -> orchestrator freezes data and incumbent -> optimizer sees redacted training/dev only -> stage typed patch -> dev paired rollouts -> select one -> sealed service evaluates fresh fixtures and anchor suite -> trusted gate emits eligible/rejected/inconclusive -> user views diff/report and optionally approves -> gate transaction CAS -> new tasks use new policy -> verify restart -> rollback. No production activation from fake demo. On insufficiency show reason and no change. Learner/evaluator have separate budgets; learning never blocks normal chat or grants itself authority.

## Sequence C: durable event (M2)

Authenticated webhook -> transactional inbox dedup -> trusted resource/version -> scheduler lease -> execute read-only observation -> wait predicate and release worker atomically -> matching event wakes task once -> reload pinned version and current grant -> finish or reconcile. Simultaneous update on same resource triggers stale-result handling; no review approval based on old commit. Test duplicate events, wake-before-wait, cancellation, lease expiry, event cascades and daemon restart. Idle inference count zero.

## Acceptance artifacts

M0: install from source, fake-provider offline chat, one real configured endpoint opt-in, read authorized file, create private artifact, persisted result/usage/receipt, bounded failures, no credential leakage. M1: deterministic normalization demo with baseline fail, validated patch, dev selection, sealed unseen improvement, harmful candidate rejection, explicit approval, new task policy change, restart, rollback, no-feedback abstention. Live mode may fail to improve and must report that. M2: signed event and crash matrix. M3: GitHub read-only review plus second domain. P2: matched-budget experiments.

## Research experiment plan

Compare B0 plain tool loop, B1 fixed runtime, B2 memory only, B3 naive reflection, B4 GEPA or other compatible optimizer, B5 full H4. Use same base model/version, allowed tools, task families, initial data, rollout and optimization budget. Separate dev/holdout by task source; publish fixture provenance and code, no private traces without consent. Metrics: exact task success, useful verified findings, false positives, intervention rate, quality vs total inference/learning cost, latency, retention on anchors, failures/unknown effects. Report paired intervals and independent group counts, all seeds, model dates, missing cases, negative results. Test H-A component-local interventions vs broad patches; H-B scoped overlays vs global changes; H-C operator setup effort and portability; H-D value-based schedule vs always optimize. Ablate manifest, evidence lineage, scoped retrieval and anchor gate. Do not compare reported benchmark numbers across different model/budget settings as superiority evidence. External project integration requires license audit, pinned upstream revision and adapter conformance; retain simple fallback optimizer.

## Repo CI

Credential-free unit and integration tests on every PR; schema fixtures, type/lint/import boundaries, SQLite restart and fault tests, security negatives; opt-in paid smoke tests never run on untrusted fork with secrets. Release only after docs and reproducibility checks. A green pure-contract suite is not a green runtime suite. No placeholder endpoint may return successful fake result outside explicit demo mode.
