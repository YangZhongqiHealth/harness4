# Implementation status

Updated 2026-11-24. Public MIT-licensed PR workflow alpha:
https://github.com/YangZhongqiHealth/harness4

| Work | Status | Evidence |
|---|---|---|
| H4-001 | Contract implementation complete; independent review not recorded | Typed records, scoped Protocols, JSON Schema and wire fixtures |
| PR workflow alpha | Implemented | `h4 ship`, commit-pinned reports, observe policy, offline fixture mode, bounded text-only model review |
| H4-002 | Implementation complete; live endpoint qualification pending | Typed model port, fake/compatible adapters, validated tools and structured output, SSE, declared/probed capabilities, offline doctor |
| H4-003 | Ready, not implemented | Persistence is the next dependency-ready foundational issue |
| H4-004–025 | Not implemented | Follow original dependency graph; do not infer completion from the PR CLI |
| Open-source packaging | Published | MIT, contribution/security docs, CI, safe offline Actions example, built wheel and installed CLI smoke test |

Validation: `python -m pytest -q` — 145 passed (Python 3.12 locally).
Prior alpha GitHub CI passed tests, CLI smoke checks and package builds on Python 3.11, 3.12
and 3.13 for implementation commit `6bbb60d`.
CI: https://github.com/YangZhongqiHealth/harness4/actions/runs/45542186257
The wheel built successfully and its installed `h4 --help` works. No live model call
or provider-quality benchmark has been run. The adapter is tested with HTTP mocks.

The CLI compares committed changes, optionally calls the selected model, and prints
JSON. It does not modify reviewed code, post reviews, repair CI, approve or merge.
CI evidence is operator supplied; recommendations are advisory. The broader durable
assistant and learning runtime remain unimplemented. See planning/RELEASE.md.

Current increment: model gateway 0.4.0a0. See docs/PROVIDERS.md and
planning/PRODUCT.md. Current remote CI is recorded after publication.
