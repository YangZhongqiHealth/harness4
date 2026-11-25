# SPEC-00 — Canonical contracts, invariants and dependency rules

Status: normative target for P0; executable subset in `src/harness4/contracts.py` and `tests/test_contracts.py`. Other contracts are specified here and must be implemented before consumers depend on them. Master RFC §§4–5, 10–12, 14.

## Identity and ownership

| Record | Identity | Owner / mutation rule |
|---|---|---|
| AgentDefinition | workspace + agent + revision | operator writes immutable revisions |
| Session | workspace + session | application owns ordered messages |
| Task | task_id + workspace | kernel writes transitions with expected version |
| Run | run_id + task + fence | lease manager owns; not reused after takeover |
| Step | task + monotonically increasing sequence | kernel append only |
| Operation | stable operation_id derived from task + logical step | ledger state, same across retry |
| PolicyBundle | canonical SHA-256 of validated content | policy registry append only |
| KnowledgeView | version/hash + ACL scope | knowledge service; separate from policy |
| Candidate | candidate hash + parent policy hash + patch | candidate registry append only |
| Dataset/EvalProtocol | content digest + version | trusted evaluator data owner |
| Evidence | provenance ID + task/policy/artifact refs | collector append; deletion tombstones |
| Release | immutable record + active pointer | trusted gate alone may update pointer |

Use opaque UUIDs in production; caller idempotency keys are not resource identifiers. Namespace by workspace at repository lookup, not by string formatting alone. IDs cannot confer authorization. Stable request fingerprints use canonical serialization (sorted keys, compact JSON, UTF-8; no NaN; normalized timestamps; no secrets). This project-local canonicalization is not RFC 8785; if cross-language hashing is added, version the canonicalizer and migrate explicitly. Hashes exclude mutable database timestamps unless semantically required. Store schema_version and canonicalizer version. Immutable Pydantic records do not automatically deep-freeze dictionaries; executable subset uses tuple fields for policy contents.

## Ports and imports

`contracts` → no implementation imports; `ports` → contracts; `kernel` → ports; `application` → kernel/ports; `adapters` → ports; `execution` → context/model read interfaces; `learning` → evidence read + candidate proposal + dev evaluation interfaces; `release` → trusted scorecard + active pointer repository. CLI and HTTP call application only. Learner has no release writer or live tool broker. Real isolation requires process credentials, not just imports.

## Required service interfaces (async unless pure)

```python
class TaskService(Protocol):
    async def submit(self, principal, spec, request_key) -> AdmissionReceipt: ...
    async def get(self, principal, task_id) -> TaskView: ...
    async def cancel(self, principal, task_id) -> TaskView: ...
    async def events(self, principal, task_id, after_seq) -> AsyncIterator[Event]: ...
class StatePort(Protocol):
    async def load(self, task_id) -> Snapshot: ...
    async def commit(self, lease, expected_version, transition, events, effects) -> Snapshot: ...
class PolicyReadPort(Protocol):
    async def resolve(self, agent_id, family) -> PolicyView: ...
    async def load(self, policy_hash) -> PolicyBundle: ...
```

Other ports are defined by component specs. All boundary records carry schema version. Return typed domain errors: INVALID_INPUT, UNSUPPORTED_CAPABILITY, NOT_AUTHORIZED, CONFLICT, BUDGET_EXHAUSTED, TIMEOUT, TRANSIENT_PROVIDER, INVALID_MODEL_OUTPUT, UNKNOWN_EFFECT, INSUFFICIENT_EVIDENCE, STALE_CANDIDATE. Errors contain safe user-facing message, retryability and correlation ID; do not leak raw credentials or provider bodies. Retry only by kernel, not simultaneously by every adapter. Unknown external effect is a distinct status, never a successful receipt.

## Task semantics

Admission pins `policy_hash`, definition revision, model/profile, tool manifest, outcome spec. Task may have no session. New run gets new fence; root budget shared across children. Revocation checks at dispatch regardless of pin. State transitions require expected version and, if running, live fence. Model/tool calls outside DB transactions. Persist result then reduce; consume committed responses before issuing new calls. Terminal task cannot resume except explicit audited reconciliation of UNKNOWN_EFFECT; a retry creates linked task. On cancellation in-flight effects may occur: return partial receipts and do not claim undo.

## Compatibility and schema tests

Fixtures must cover request/result round trip, unknown enum, malformed tool input, version mismatch, absent usage, stream reconnect, stale revision, policy patch base mismatch and unknown field. External requests reject unrecognized authority fields. Adding optional fields is compatible only with declared version policy; incompatible semantic changes require migration. Do not place secrets, chain-of-thought, sealed labels or raw tool auth headers in serialized objects. Release changes to contracts require reviewed ADR and fixture update.

## Version-1 implementation baseline

H4-001 implements the task/result/event/error records and service Protocols in
`src/harness4/contracts.py` and `src/harness4/ports.py`. See ADR 0001's dated
implementation decisions for timestamp encoding, scoped read signatures and the
result pin field. `tests/fixtures/contracts-v1.json` is the JSON Schema baseline;
`tests/fixtures/records-v1.json` contains valid wire examples. Every concrete record
is round-tripped and tested for unknown fields and incompatible schema versions.
These are interfaces and validation, not working runtime services. Provider stream
and tool argument conformance fixtures are delivered with their respective adapters.
