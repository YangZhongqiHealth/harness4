# Validation

Current baseline: **289 tests** for 0.6.0a0. CI runs on Python 3.11–3.13 and checks
installed CLI commands, examples and package builds.

## Reproduce

From the repository root, in an activated Python 3.11+ environment:

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
python examples/learning_demo.py
python examples/provider_tools.py
python examples/durable_task.py
```

Ordinary tests and these examples need no model or GitHub credentials. The learning
demo uses temporary storage and scripted model replies.

## Coverage

| Area | What the tests exercise |
|---|---|
| Contracts and schemas | Record round trips, unknown fields, version mismatches, canonical encoding and import boundaries |
| Local review | Real temporary Git histories, commit pins, protected paths, size/binary limits, policy reports and malformed model output |
| Providers | Tool/structured-output validation, SSE boundaries, UTF-8 splits, refusal/truncation, timeouts, unknown usage, no retry/redirect and capability probes |
| Persistence | Real SQLite transactions, scoped reads, fences, immutable receipts, pending effects, process crashes, locks and artifact integrity |
| GitHub workflow (61 cases) | Review → repair → new-head review → CI → approval, restart deduplication, reconciliation, stale evidence, separate principals and protected paths |
| Learning (43 cases) | Immutable evidence, development-only proposals, fresh release cohorts, confidence gates, approval expiry/replay, activation, rollback and feedback retraction |

A synthetic 202-case learning integration makes 809 HTTP-mocked model requests
through the real adapter and evaluator. It promotes a candidate, uses it through the
GitHub CLI, rolls it back and verifies persisted effect deduplication. This exercises
the production gate's mechanics; constructed data is not an independent real-PR sample.

## Recorded evidence

- Local check on 2026-11-26: `python -m pytest -q` — 289 passed.
- [CI for d97007b](https://github.com/YangZhongqiHealth/harness4/actions/runs/45883506880):
  Python 3.11–3.13 tests, installed smoke checks and package builds passed.
- The 0.6.0a0 wheel was also installed in a separate smoke environment; CLI help,
  learning demo and installed learning/GitHub integration tests passed outside the
  source checkout.

The CI link records that revision, not future changes. See the repository's
[CI runs](https://github.com/YangZhongqiHealth/harness4/actions/workflows/ci.yml)
for current results.

## What remains unverified

GitHub tests simulate HTTP responses and model replies while using real local state.
No live model/GitHub repair-and-approval qualification or paid quality benchmark is
recorded. Test counts do not establish accuracy, provider compatibility, sandbox
security or improvement over Claude Ship. Local locks do not establish distributed
coordination. A scripted learning demo verifies the lifecycle, not live learning gains.

See [status](../docs/STATUS.md), [roadmap](../docs/ROADMAP.md) and
[security boundaries](../SECURITY.md).
