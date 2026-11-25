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
