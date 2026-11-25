# Harness4

**Open, model-portable PR review and auditable policy reports. MIT licensed.**

Harness4's first usable alpha reviews a committed Git diff and produces a structured,
commit-pinned report. Run it locally with your chosen Chat Completions endpoint, or
try the offline policy workflow without a model or API key.

Our direction is an open-source alternative for the review → fix → approval workflow
introduced by [Claude Ship](https://claude.com/resources/articles/introducing-claude-ship).
Today we implement **local advisory review plus an opt-in GitHub review → repair →
approval loop**. The GitHub command posts reviews, creates bounded repair commits,
waits for actual CI and can approve with a separate account and trusted policy. There is no
claim of feature parity or better review accuracy. This independent project is not
affiliated with Anthropic.

## Install from this repository

Python 3.11+ and Git are required:

```sh
git clone https://github.com/YangZhongqiHealth/harness4.git
cd harness4
python -m venv .venv
source .venv/bin/activate
python -m pip install .
h4 --help
```

The package is not published to PyPI; install this checkout rather than an unrelated
package with the same name. Windows users can activate `.venv\Scripts\activate`.

## Try it without a key

Against any Git repository with at least two commits:

```sh
h4 ship --repo /path/to/your/repo --base HEAD~1 --head HEAD
```

It emits JSON with the exact commit IDs, diff and policy digests, changed files,
change size, CI evidence, and reasons for human review. No model is called unless
`--model` is supplied. To exercise a scripted review:

```sh
h4 ship --repo /path/to/your/repo --base HEAD~1 \
  --review-file examples/review.json --checks passed
```

Fixture output is marked `fixture` and can never yield an eligible recommendation.
Only committed changes are included; uncommitted files are not reviewed. For a PR,
pass its merge-base commit as `--base` and the PR head commit as `--head`.

## Review with your model

Set `H4_MODEL_KEY` in your environment using your preferred secret manager, then:

```sh
h4 ship --repo /path/to/your/repo --base HEAD~1 \
  --model YOUR_MODEL_NAME --base-url https://YOUR_PROVIDER/v1 \
  --policy examples/ship-policy.json --checks unknown > report.json
```

This sends the changed filenames and diff to the explicitly selected endpoint and
may incur provider charges. Use `--key-env OTHER_KEY_VARIABLE` for another credential
reference. Loopback HTTP endpoints are supported for local models. Remote endpoints
require HTTPS. Each invocation makes at most one request, with a default 60-second
wall-clock timeout, 4,096-token output ceiling and a 200 KB diff limit. Binary diffs
are rejected for human review. There are no retries, redirects or endpoint fallback.

The text-only adapter requires a complete JSON review. Refused, truncated, malformed,
or tool-call responses fail with a safe error and exit code 2. Missing token usage
stays unknown. Real-provider conformance has not yet been tested; compatible endpoint
and model behavior varies. See the [Chat Completions protocol reference](https://developers.openai.com/api/reference/resources/chat).

## Model gateway and capability checks

The SDK now supports validated native tool calls, structured output, buffered SSE
streaming, and a deterministic fake provider. The `ship` command remains read-only
and text-based; model tool support does not execute tools or authorize repairs.

```sh
# Inspect declarations without network access or an API key.
h4 doctor --offline --model YOUR_MODEL --base-url https://YOUR_PROVIDER/v1

# Optional: explicitly authorize up to five small model requests to test declared capabilities.
h4 doctor --probe --model YOUR_MODEL --base-url https://YOUR_PROVIDER/v1 \
  --native-tools --streaming --structured-output --usage-reporting

# Credential-free SDK example.
python examples/provider_tools.py
```

See [provider contracts and conformance](docs/PROVIDERS.md) for limits, capability
semantics and SDK behavior. A successful probe tests basic protocol exchanges;
review quality still requires independent evaluation.

## Durable state SDK

The local state repository provides SQLite task/event/operation transactions,
request idempotency, run fencing, persisted results and digest-verified private
artifacts. The GitHub workflow uses this store for durable write intents, receipts and recovery;
the local `ship` command remains advisory.

```sh
python examples/durable_task.py
```

See [persistence and recovery semantics](docs/PERSISTENCE.md). Trusted admission,
general authorized tool execution and the broader runtime remain future layers.

## What a local recommendation means

`eligible` is advisory: a completed model review, supplied passing CI evidence, no
blocking findings, and a change within the configured path/size limits. It is not a
GitHub approval. The model can miss defects; findings have not undergone independent
verification. `--checks` is operator-supplied evidence, not a GitHub status query.

Observe mode exits 0 when a report was produced, including `needs_human`; failures
exit 2. Do not use its exit code as a required merge gate. The local `ship` command does not execute code, modify files, push commits, approve
or merge. The separate GitHub command can write only when explicitly enabled.
Keep policies in a trusted checkout; never let the reviewed PR choose its own policy.

## GitHub review, repair and approval

`h4 ship-github` connects to a real GitHub repository using an operator-owned policy
and a private persistent journal. Start with observation, then enable bounded repairs
and a separate approval account. See the [setup, example and recovery guide](docs/GITHUB_WORKFLOW.md).

```sh
h4 ship-github --policy /trusted/project-policy.json --pr 42 \
  --state-dir "$HOME/.local/state/harness4/project" \
  --model YOUR_MODEL --base-url https://YOUR_PROVIDER/v1 \
  --write --approve --check-polls 20
```

This requires configured credentials, policy grants, trusted CI and branch protection;
copying the command alone does not enable writes. The loop supports same-repository
text PRs and does not merge. Tests cover the HTTP/state lifecycle offline; live
provider/GitHub qualification and review-quality benchmarks remain pending.

## GitHub Actions

[The observe workflow example](examples/ship-observe.yml) uses read-only permissions,
installs trusted base-branch code, reads the PR diff, and uploads the report. It needs
no model secret and therefore reports `needs_human`. Copy it after Harness4 is present
on your default branch. Do not add secrets to untrusted PR code or switch this example
to `pull_request_target` with a PR checkout.

## Development and roadmap

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [current status](planning/STATUS.md), and
[release plan](planning/RELEASE.md), and [full product acceptance gates](planning/PRODUCT.md). The original [harness design](docs/DESIGN.md) and
[dependency backlog](planning/ISSUES.md) remain the longer-term architecture. Their
proposed assistant/learning commands are not implemented. Contract tests do not
establish runtime security, durable execution or learning effectiveness.

Next: qualify the GitHub loop with real providers and PRs, improve finding verification,
add isolated CI-failure repair and GitHub App onboarding, then benchmark quality.
