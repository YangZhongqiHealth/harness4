# ADR 0001 — Core contracts, model gateway and local state

Accepted implementation baseline for the public alpha. Updated 2026-11-26 to
separate implemented decisions from the superseded general-runtime proposal.

## Context

PR coordination needs stable review identity, bounded provider calls and durable
records of external effects. These foundations must remain independent of a model
vendor and must not imply authorization merely because a record is schema-valid.

## Contract decisions

- Python 3.11+, Pydantic v2 records and async Protocols define component boundaries.
  Core records do not import provider SDKs or storage implementations.
- Version-1 records reject unknown fields and incompatible schema versions. Tuple
  collections avoid mutable boundary containers. Checked-in schemas and valid wire
  examples provide compatibility tests for each concrete record.
- `TaskResult.policy_hash` identifies the pinned policy. Verification is separate
  from execution status. Unknown model usage is `None`, not zero.
- Event timestamps use validated UTC `YYYY-MM-DDTHH:MM:SS.ffffffZ` strings.
  Canonical JSON is project-specific, not RFC 8785; cross-language hashing would need
  explicit compatibility and migration work.
- Scoped reads take workspace identity. Leases include workspace, task, run and
  fence. Storage implementations enforce scope, expected versions and live fences.
- General task-service Protocols are not implemented application services. Future
  admission must reject disagreement between the request key argument and the key
  in `TaskSpec` before persistence.

## Model gateway decisions

Model records and ports are separate from adapters. Tools and output schemas use
immutable canonical JSON strings validated as inline JSON Schema 2020-12; schema
references are deliberately unsupported. Unsupported modalities require new contracts.
Logical request and attempt IDs remain distinct.

Tool calls are exposed only after a complete response. Partial streamed text is
advisory; refused, truncated or malformed responses cannot yield dispatchable calls.
A tool proposal grants no execution authority. Capabilities distinguish configured
declarations from explicitly requested bounded probes.

Adapters make one attempt and do not retry or redirect. A caller must own retry
budgets, deadlines and ambiguous-usage accounting. This avoids multiplying retries
across layers. Offline diagnostics make no model request; paid probes require opt-in.

## Persistence decisions

SQLite uses WAL/FULL, schema version 1 and a single-coordinator OS lock. A metadata
row records canonicalizer version 1. Data keys and reads are workspace-scoped.
Matching request retries retain their original task/policy pin. Restart takeover
increments local fences and preserves pending intents for reconciliation.

State, steps, events, intents and optional final results share a transaction.
Receipts are committed separately before reduction and cannot be rewritten.
Unresolved effects cannot silently become successful terminal tasks. Artifacts are
content-addressed and fsynced before their references are committed; orphan cleanup
is explicit and scoped.

## Consequences

The design supports inspectable local recovery without requiring a distributed
scheduler or hosted orchestration. It does not make remote effects atomic or
exactly-once. Filesystem and symlink checks are defense in depth, not a sandbox
against processes running as the same OS user.

See [architecture](../DESIGN.md), [provider contract](../PROVIDERS.md),
[persistence](../PERSISTENCE.md) and [learning decisions](0002-review-learning.md).
