# Local review reference

`h4 ship` reviews a committed Git diff and emits a structured, commit-pinned JSON
report. It is read-only and advisory. Uncommitted files are not included. The
separate [GitHub command](GITHUB_WORKFLOW.md) handles remote review/repair/approval.

## Install and inspect a change

Follow the [README quickstart](../README.md#quickstart). Windows users can activate
the virtual environment with `.venv\Scripts\activate` (or `Activate.ps1` in PowerShell).
The package is not published to PyPI; install the repository checkout.

Against a repository with at least two commits:

```sh
h4 ship --repo /path/to/your/repo --base HEAD~1 --head HEAD
```

For a PR, supply its merge-base commit as `--base` and the PR head as `--head`.
Without `--model`, the command makes no model request. It reports exact commit IDs,
diff/policy digests, changed files, change size, supplied CI evidence and reasons for
human review. It does not claim an AI review occurred.

## Review with a model

Set `H4_MODEL_KEY` using your preferred secret manager, then:

```sh
h4 ship --repo /path/to/your/repo --base HEAD~1 --head HEAD \
  --model YOUR_MODEL --base-url https://YOUR_PROVIDER/v1 \
  --policy examples/ship-policy.json --checks unknown > report.json
```

Example paths assume you are in the Harness4 checkout. `--key-env OTHER_KEY_VARIABLE`
selects another credential reference. The changed filenames and diff are sent to the
explicitly selected Chat Completions-compatible endpoint and may incur charges.
Loopback HTTP endpoints are supported for local models; remote endpoints require HTTPS.

Each invocation makes at most one model request, with a default 60-second wall-clock
timeout, 4,096-token output ceiling and 200 KB diff limit. Binary diffs are rejected.
There are no retries, redirects or endpoint fallback. The text-only adapter requires
a complete JSON review. Refused, truncated, malformed or tool-call responses fail
with a safe error. Missing usage remains unknown. Live endpoint qualification is
still pending; compatibility varies by provider and model.

The SDK separately supports native tools, structured output and buffered SSE.
Those capabilities do not authorize repairs or execute model-proposed tools.
Use [provider diagnostics](PROVIDERS.md) to inspect or explicitly probe capabilities:

```sh
h4 doctor --offline --model YOUR_MODEL --base-url https://YOUR_PROVIDER/v1
```

## Fixtures and recommendation semantics

For a scripted review, run from the Harness4 checkout against a compatible fixture:

```sh
h4 ship --repo /path/to/your/repo --base HEAD~1 \
  --review-file examples/review.json --checks passed
```

Fixture output is marked `fixture` and never yields an eligible recommendation.
`eligible` from a model review is advisory: it requires supplied passing CI evidence,
no blocking findings and a change inside the configured path/size bounds. The model
can miss defects. `--checks` is operator-supplied, not a GitHub status query.

Observe mode exits 0 when a report was produced, including `needs_human`; failures
exit 2. **Do not use the exit code as a required merge gate.** The command does not
execute code, modify files, push commits, approve or merge. Keep policies in a trusted
checkout; do not let the reviewed PR select its own policy.

For opt-in learned review guidance, use
[`ship-github --learning-dir`](LEARNING.md). Local `ship` does not load learned policies.
