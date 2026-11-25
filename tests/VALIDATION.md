# Validation

2026-11-24: `python -m pytest -q` — **83 passed** on Python 3.12.

- Original 44 contract/schema/import tests.
- 39 PR workflow tests: real temporary Git histories, commit pins, protected-path
  renames, binary/oversize rejection before dispatch, offline/fixture reports,
  policy eligibility, malformed review JSON, mocked CLI model path, unknown usage,
  safe provider errors, no retry/redirect, refused/truncated/tool output rejection,
  malformed/oversize responses, endpoint restrictions and absolute timeout.
- Built `harness4-0.3.0a0-py3-none-any.whl` with `pip wheel --no-deps
  --no-build-isolation`; installed into a temporary venv and ran `h4 --help`.
- Scanned distributable source for common secret formats and local user paths:
  no matches. This pattern scan is not a guarantee that arbitrary secrets are absent.

GitHub CI passed all Python 3.11, 3.12 and 3.13 jobs (tests, installed CLI smoke
and package build) for implementation commit `6bbb60d`.
Run: https://github.com/YangZhongqiHealth/harness4/actions/runs/45542186257. No real model endpoint, benchmark quality, automatic
repair, durable runtime, authorization enforcement or trusted approval gate was
validated. Reports are observe-only and CI evidence is operator supplied.


## Model gateway increment — 0.4.0a0

`python -m pytest -q`: **145 passed** locally on Python 3.12 (83 existing tests plus
62 model conformance/schema tests). New checks cover native tool/result round trips,
unknown/duplicate/malformed arguments, stable IDs, inline schema restrictions,
structured output, split UTF-8 and SSE arguments, missing terminators, changed IDs,
disconnect/cancellation, response bounds, expired deadlines, offline diagnostics,
fake exhaustion, bounded probe lifecycle, schema compatibility and import direction.

The offline doctor and fake SDK example both ran successfully. No live provider,
paid probe, code execution broker or repair workflow was exercised. Previous alpha
CI results above apply to the earlier implementation, not automatically to this one.


## Local persistence increment — 0.4.0a0

Current suite: **185 tests** including SQLite migration/WAL configuration, scoped
reads, idempotent requests, immutable policy pins, atomic event/state/result commit,
late-failure rollback, stale fences, immutable receipts, pending-effect reconciliation,
restart and actual process-crash recovery, second-coordinator refusal, result/artifact
namespace checks, digest corruption, symlink/FIFO negatives, orphan collection and
state schema compatibility. `examples/durable_task.py` demonstrates persisted output
retrieval after restart without model calls. These checks do not implement or certify
the eventual tool sandbox, application authority resolver or distributed scheduler.


Model gateway + SQLite implementation commit `e8421fb` passed all GitHub CI jobs
on Python 3.11, 3.12 and 3.13 (183 tests, offline doctor, both installed SDK examples,
and package builds):
https://github.com/YangZhongqiHealth/harness4/actions/runs/45671254294

The follow-up Git subprocess bound adds two tests (185 total locally): output is
limited during reading and a timed-out child is terminated. It does not change
model, state or authorization semantics.


## GitHub lifecycle increment — 0.5.0a0

The complete suite now has 246 tests; 61 cover GitHub workflow behavior with an
httpx simulated server and real SQLite journal. Integration coverage includes the
CLI, two review passes, repair commit/tree/ref APIs, a fresh-head review, required
App-pinned checks, separate-user approval, and restart without duplicate effects.
Negative cases cover changed head/base/CI, stale approval dismissal, copied reviews,
unknown network outcomes, evidence-only reconciliation, repair exhaustion, protected
and invalid paths, symlinks/submodules, unsupported PR types and transport bounds.

No live model, GitHub mutation, fork deployment, sandbox escape or comparative quality
benchmark was run. Mocked success validates orchestration, not provider/GitHub account
configuration or model correctness. Previous SDK/crash tests remain in the full suite.

The 0.5.0a0 wheel built offline and was installed into a separate smoke environment.
The installed `ship-github --help` and all 61 GitHub integration tests passed from
outside the source checkout, with repository pytest configuration disabled.
