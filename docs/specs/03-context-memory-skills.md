# SPEC-03 — Context compiler, memory and skills

Master RFC §§7–8, 11. Depends SPEC-00/01/02. Reference patterns: Hermes progressive disclosure, ACE/ExpeL experience and Agent Skills. P0 retrieval deterministic FTS or lexical matching; no extra embedding credential. No automatic skill code execution.

## Compile contract

`compile(snapshot, policy_view, capability_profile, grant_view, knowledge_view) -> (ModelRequest, ContextManifest)`; read-only ports. Inputs: trusted instructions, task goal/constraints, user-visible history, pending tool call/result blocks, observations and references, applicable scoped memory/skill candidates. Output manifest includes model/profile, policy hash, knowledge view hash, selected IDs/revisions, retrieval reason/scores, token estimates by bucket, omissions and compression record. Audit only permitted metadata/content; no secrets. Freeze knowledge for evaluation; in production capture each live view. Security revocation overrides pins and invalidates affected context.

Algorithm: (1) reserve output and provider overhead; (2) include non-negotiable instructions, task and required tool pairing; reject if these cannot fit; (3) ACL and egress-filter sources before retrieval; (4) rank remaining history, facts, lessons, skills by task relevance and scope, select within budget; (5) load skill detail progressively; (6) compact old history without losing unresolved requests or authoritative receipts; (7) validate authority/provenance and final size; (8) record manifest before inference. External content is data not instruction; source labels are not a security boundary. Never truncate tool call/result pairs into invalid provider transcripts. If compaction uses a model, budget it, store summary lineage and do not treat generated summary as verified fact.

## Memory records

Fields: id, scope, kind (fact/preference/episode/lesson), content/ref, provenance, verification, created/expiry, supersedes, ACL, knowledge revision. Facts and preferences explicitly supplied by user may be stored with consent; inferred rules are hypotheses. Session projection separate from task state. Episodic entries link outcome and manifest, not unredacted raw traces. Procedural knowledge resides in versioned skill/ policy. Resolve contradictions by explicit correction superseding previous record; do not concatenate inconsistent facts. Retrieval: scope and authority filter first, lexical score + bounded recency, deterministic ties. No cross-workspace default. Deletion propagates to derived records and future learning snapshots; candidate using deleted evidence must be invalidated or re-evaluated under retained permitted evidence. Retained immutable metadata may be tombstoned; already disclosed provider data cannot be guaranteed erased locally.

## Skills

Read-only `SkillRegistry.resolve(task_family, grant_view)` returns manifest + versioned content. Package compatible with `SKILL.md` and references; add manifest with required capabilities, applicability, input/output schema refs, provenance and verification. Skills cannot grant tools. P0 ships built-ins only, M1 learns named instruction sections. P2 candidate skills can be created as text; executable files only from operator-installed reviewed packages. Use explicit selectors rather than global concatenation. A learned skill must be evaluated on target and unrelated anchor cases before promotion. Candidate is not visible to actor until activated. Prefer skill load on demand rather than putting all procedures in system prompt.

## Acceptance

Oversized context either compacts safely or returns explicit error. Test ACL before ranking, same-scope version selection, conflicting facts, revoked grants, omitted memories, missing tool-pair preservation, deterministic retrieval ties, no extra embedding calls, redaction, deletion invalidating candidate. Manifest must identify exact policy/knowledge versions and selected sources. Benchmark later: fixed prompt vs manifest-informed retrieval optimization with matched budgets and holdout. No claimed quality advantage until measured.
