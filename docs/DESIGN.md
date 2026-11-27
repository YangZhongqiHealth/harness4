# Architecture

Harness4 is a local Python coordinator for PR review, bounded repair, policy-gated
approval and opt-in review-checklist learning. This page describes the implemented
alpha. Future capabilities are tracked in the [roadmap](ROADMAP.md).

## Components

| Component | Responsibility | Source |
|---|---|---|
| CLI | Dispatch local review, GitHub workflow, provider diagnostics and learning commands | [cli.py](../src/harness4/cli.py) |
| Local review | Read committed Git changes and produce an advisory report | [ship.py](../src/harness4/ship.py) |
| GitHub coordinator | Bind review, repair, CI and approval to PR revisions and operator policy | [github_workflow.py](../src/harness4/github_workflow.py) |
| GitHub adapter | Bounded REST requests and response validation | [github.py](../src/harness4/github.py) |
| Model gateway | Normalize model requests, responses, usage and capability errors | [model_ports.py](../src/harness4/model_ports.py), [adapters](../src/harness4/adapters) |
| Durable state | SQLite transactions, scoped records, fences, receipts and private artifacts | [sqlite_state.py](../src/harness4/adapters/sqlite_state.py) |
| Learning engine | Propose checklists, evaluate candidates and enforce release gates | [engine.py](../src/harness4/learning/engine.py) |
| Learning store | Persist evidence, candidates, approvals, active versions and revocations | [store.py](../src/harness4/learning/store.py) |

## PR execution

The local `ship` command reads a committed diff and emits a structured report.
It does not write to the repository or load learned guidance.

The `ship-github` coordinator reads a same-repository PR under a trusted operator
policy. Model findings can lead to bounded text replacements in allowed changed
regular files. Repairs use single-parent commits and non-force branch updates.
The coordinator reviews the new revision and reads CI for the exact head and
configured check names/App IDs before optional approval. Approval uses a different
GitHub user from both the writer and the PR author, with classic branch protection.

Write intent is persisted before dispatch; receipts record observed effects.
Uncertain outcomes stop automatic retries. Read-only reconciliation can recover
receipts from sufficient GitHub evidence. GitHub does not offer an atomic
head/check/review transaction, so freshness checks cannot guarantee exactly-once
remote effects or eliminate all races.

See [GitHub workflow and recovery](GITHUB_WORKFLOW.md) for configuration and limits.

## Review learning

Learning uses a separate store from the write journal. A review pins one checklist
and records an episode. Verified, revision-bound labels become evaluation evidence.
The proposer sees development examples and can change only a bounded checklist
section; it cannot change model identity, credentials, permissions or evaluation rules.

Candidate selection uses development data. A separate release evaluation compares
one candidate with the incumbent on fresh target and regression cohorts. Cohorts are
consumed before release calls; incomplete runs cannot reuse them. Eligibility requires
the configured confidence and retention gates, then explicit operator approval.
Activation is transactional. Rollback restores a compatible prior version; retracting
feedback revokes dependent policies and restores baseline when needed.

This separation is enforced by code and data flow inside a trusted local process,
not by an OS sandbox. See [learning operations](LEARNING.md) and
[ADR 0002](adr/0002-review-learning.md) for the statistical and trust boundaries.

## Contracts and compatibility

Pydantic records and Protocols separate core data from provider and storage adapters.
Versioned JSON Schema and wire fixtures live in [tests/fixtures](../tests/fixtures).
Schema validation is not authorization. Some general task-service interfaces exist
without application implementations; their presence does not provide a general
agent runtime, chat service or tool executor.

[ADR 0001](adr/0001-p0-decisions.md) records implemented serialization, provider and
storage decisions. Intentional contract changes require corresponding fixture updates.

## Trust and deployment

- The operator controls policy, credential references, state directories and datasets.
- PR content and model outputs are untrusted inputs; neither grants write authority.
- The coordinator does not execute PR code. Tests run in separately configured CI;
  the operator is responsible for CI runner isolation.
- Local filesystem protections and OS locks do not isolate processes sharing the
  same OS identity. Each store permits one coordinator at a time.
- Provider compatibility and model quality require live qualification; scripted
  adapter tests do not establish either.

[Provider contract](PROVIDERS.md) · [Persistence](PERSISTENCE.md) ·
[Security policy](../SECURITY.md) · [Current status](STATUS.md)
