# SPEC-02 — Kernel, persistence, task scheduling and recovery

Master RFC §§6, 10, 15. Depends SPEC-00; provider and tool adapters injected. Single coordinator P0, durable events/leases M2. Reference patterns: Temporal durable activities and LangGraph checkpoint/interrupt, not dependencies in first release.

## Database and transactions

SQLite WAL, foreign keys on, busy timeout, schema migrations; private data directory. Tables: agents, definitions, sessions, tasks (status, state_version, pinned_policy, lease_fence), requests (workspace/key unique, fingerprint, task_id), steps (task/seq unique), operations (logical ID unique, intent hash, state, receipt), events (task/seq unique), artifacts, budget_accounts/reservations, policy_bundles, active_pointers, feedback, candidates, eval_runs, releases. M2 adds inbox (source/delivery unique), outbox, waits, resource_leases. One writer coordinator; transaction commits state + event + outbox atomically. No provider/tool network calls inside transaction. Atomic private artifact temp-file write + rename, hash verification, then reference commit; orphan files swept later. SQLite backup API, not naive copy of live DB. Backup restore never implies external action undone.

## Execution algorithm

```text
admit -> persist task and policy pin -> lease -> load snapshot
-> consume pending committed response / reconcile outstanding intent
-> compile context -> reserve model budget + persist request intent
-> call model outside transaction -> commit normalized response/usage
-> reducer selects next typed command -> authorize + persist tool intent
-> execute/reconcile outside transaction -> commit receipt
-> finish or advance; bounded by deadline, turn limit and root budget
```

Pure reducer computes next state/command from committed events. Actor proposes calls/finish/ask/wait, not grants. P0 may run serially without distributed leases but uses state_version and stable logical IDs; M2 adds fenced worker lease and resource lease. Concurrency keys derive from trusted environment metadata; read-only work can share, conflicting writes serialize. Coalesce only replaceable updates (e.g. head revision), never drop approval or nonreplaceable feedback. Task cancellation checked before reservation/dispatch and after effect receipt; parent cancellation propagates. Waiting does not spend tokens; registration and existing inbox match must be atomic to avoid lost wakeups. Timers durable, capped retry and absolute deadline. Cause IDs + root task ID propagate to self-triggered events, budgets shared. Repeated state/error signatures can pause but domain progress predicate supplied by plugin; no universal progress metric.

## Crash matrix

| Crash point | Recovery |
|---|---|
| before intent commit | issue command anew |
| after intent, before dispatch confirmed | reconcile if write could have been dispatched |
| after effect, before receipt commit | query external state/idempotency key; do not blindly retry |
| after receipt commit, before reduction | consume committed result |
| after state commit, before UI notification | stream persisted event |
| during unknown provider usage | keep reservation or conservatively settle; never assume zero |
| expired lease with pending effect | fence old worker; reconcile before successor dispatch |

Unknown effect enters RECONCILING then UNKNOWN_EFFECT when no proof. Cancellation may produce unknown effect; report to user and require audited reconciliation. P0 local artifact create uses deterministic logical filename/idempotency and digest check. M2 remote adapter must document reconciliation guarantees and version preconditions. If absent, restrict to read-only or require operator intervention on ambiguity. Exactly-once delivery not promised.

## Budget

Integer token accounting and integer microcurrency where prices known, atomic reservation prior to calls; root task limit and descendant allocation. Reserve worst-case output and bounded input estimate; settle known actual usage, retain conservative liability if unknown. Model-only costs may be unknown for local providers; enforce token/turn/time ceilings regardless. Separate learning budget; no hidden paid optimization. Reject dispatch when budget or authorization exhausted. Root hard bounds prevent recursive event cascades.

## Acceptance

Test state-machine illegal edges, duplicate requests, stale version, crash at every effect boundary, terminal immutability, atomic event/state commit, restart and result persistence. M2 inject expired worker and simultaneous wake; exactly one logical advancement, no unsafe repeated writes. Verify two independent tasks can run concurrently but same resource writers do not overlap. Test cancellation while effect is in flight, replay after cursor, idle inference count zero. Do not implement fake `success` for missing recovery.
