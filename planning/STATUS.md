# Implementation status

Updated 2026-11-24. Public MIT-licensed PR workflow alpha:
https://github.com/YangZhongqiHealth/harness4

| Work | Status | Evidence |
|---|---|---|
| H4-001 | Contract implementation complete; independent review not recorded | Typed records, scoped Protocols, JSON Schema and wire fixtures |
| PR workflow alpha | Implemented | `h4 ship`, commit-pinned reports, observe policy, offline fixture mode, bounded text-only model review |
| H4-002 | Partial | Text-only compatible adapter; native tools, streaming, capability probes and full provider port remain |
| H4-003 | Ready, not implemented | Persistence is the next dependency-ready foundational issue |
| H4-004–025 | Not implemented | Follow original dependency graph; do not infer completion from the PR CLI |
| Open-source packaging | Published | MIT, contribution/security docs, CI, safe offline Actions example, built wheel and installed CLI smoke test |

Validation: `python -m pytest -q` — 83 passed (Python 3.12 locally).
GitHub CI passed tests, CLI smoke checks and package builds on Python 3.11, 3.12
and 3.13 for implementation commit `6bbb60d`.
CI: https://github.com/YangZhongqiHealth/harness4/actions/runs/45542186257
The wheel built successfully and its installed `h4 --help` works. No live model call
or provider-quality benchmark has been run. The adapter is tested with HTTP mocks.

The CLI compares committed changes, optionally calls the selected model, and prints
JSON. It does not modify reviewed code, post reviews, repair CI, approve or merge.
CI evidence is operator supplied; recommendations are advisory. The broader durable
assistant and learning runtime remain unimplemented. See planning/RELEASE.md.
