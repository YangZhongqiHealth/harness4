# ADR 0001 — P0 decisions and scope freeze

Status: proposed for implementation; supersedes ambiguous P0 examples in the master RFC.

| Decision | Alternative deferred | Rationale / required test |
|---|---|---|
| Single local workspace, one coordinator, SQLite WAL; separate worker processes only when needed | Distributed scheduling / multi-tenant web service | Crash recovery and transaction ownership first; second coordinator refused |
| Python 3.11+, Pydantic v2, async service ports | Provider-specific SDK objects in core | Provider fixtures enforce normalized schema |
| Native tools or text-only capability; structured JSON fallback is optional | Pretend every endpoint supports native tools | Unsupported capability is explicit; no silent tool execution |
| Default assistant uses mounted read-only files plus private artifact writes; no shell | Broad OS access | Symlink and path escape tests; provider credential not visible to tool |
| Agent policy pinned at task admission; mutable knowledge view is separately versioned | Pin per inference or silently switch on resume | New activation does not change pending task; revocation applies immediately |
| Plain named instruction-section patches only in M1 | Arbitrary skill code and workflow evolution | Strict patch validation and scope; no learner code execution |
| Fake normalization demo has deterministic outcomes; live demo needs independent labels and sufficient evidence | Automatic LLM-judge-only release | Fake eligibility cannot activate production policy |
| Human approval plus CAS activation; no auto promotion in P0 | Unattended evolution | Stale, expired, rejected, incompatible candidates never activate |
| Offline fixture environment and exact validator for first learning demo | Universal evaluator | Fresh clone per rollout, hidden answers absent from actor context |
| Record redacted observations and outputs, not hidden reasoning | Raw provider traces as learner input | Secret canary and deletion test |

Implementation sequence: M0 provides a useful bounded assistant; M1 completes the verified learning lifecycle. Minimal persistence and permissions are prerequisites, not post-M1 retrofits. M2 expands the same kernel to durable waits/events and uncertain remote effects. The terms P0/P1/P2 denote release capability tiers; M0/M1/M2 are milestones. The package skeleton is not a security boundary; the trusted coordinator must implement all access checks before use with real tools.

## H4-001 implementation decisions (2026-11-24)

The version-1 contract baseline now includes task outputs, durable display events,
safe errors and the SPEC-00 service ports. This records implementation decisions;
it does not assert independent human review or a released public SDK.

- `TaskResult.policy_hash` names the canonical pin (rather than the RFC sketch's
  ambiguous `policy_version`). Verification uses SPEC-01's four statuses and is
  independent of execution status. Unknown usage is `None`, never implicit zero.
- Boundary collections are tuples. Events carry typed display metadata and opaque
  payload references rather than arbitrary dictionaries. Event timestamps use UTC
  `YYYY-MM-DDTHH:MM:SS.ffffffZ`, validated as calendar dates; this representation
  makes timestamp serialization deterministic. Producers must redact display text.
- State and policy reads require an explicit workspace argument. A lease includes
  workspace, task, run and fence; commit receives typed intents and events.
  These signatures require implementations to check ownership, CAS and live fences;
  the records themselves provide no authorization or transactional enforcement.
- Service `events` returns an async iterator directly. Submit retains SPEC-00's
  explicit request key alongside the starter TaskSpec field; admission must reject
  disagreement before persistence. No admission service is implemented yet.
- Checked-in JSON schemas and valid wire examples cover every concrete Record.
  Schema version 1 rejects unknown fields and incompatible versions. Deliberate
  future contract changes must update this decision record and compatibility fixtures.

Provider-specific request/response/stream contracts belong to H4-002. Persistence,
active release pointers, runtime policy pin enforcement, and credential isolation
remain later issues; no implementation of those services is claimed here.

## PR workflow alpha (2026-11-24)

The user selected a usable MIT-licensed open-source PR workflow inspired by Claude
Ship. The first product slice adds isolated review/report types in `ship.py` and a
text-only provider adapter without changing the original contracts. Reports carry
base/head commit IDs and policy/diff hashes. All decisions are observe-only; fixture
reviews cannot qualify, and CI status is explicitly supplied by the operator.
No tools execute and no release pointer or GitHub approval is written. H4-002 remains
partial until its full provider interface and conformance requirements are met.
