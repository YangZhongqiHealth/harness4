<div align="center">

# Harness4

### Review. Repair. Learn. Keep control.

**Open-source PR automation with a verifiable, reversible learning loop.**

[![CI](https://github.com/YangZhongqiHealth/harness4/actions/workflows/ci.yml/badge.svg)](https://github.com/YangZhongqiHealth/harness4/actions/workflows/ci.yml)
[![MIT license](https://img.shields.io/badge/license-MIT-22c55e)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab)](pyproject.toml)
[![Alpha](https://img.shields.io/badge/status-alpha-f59e0b)](planning/STATUS.md)

[Quickstart](#quickstart) · [Choose a path](#choose-your-first-run) · [How it works](#how-it-works) · [Learning](#a-learning-loop-you-can-audit) · [Claude Ship comparison](#harness4-and-claude-ship) · [Docs](#documentation) · [Contribute](#build-with-us)

</div>

Harness4 reviews pull requests, proposes bounded repairs, checks GitHub CI, and can
approve under rules you control. Its learning loop turns verified feedback into
candidate review strategies, tests them against fresh evidence, and lets you approve
or roll back the versions used by future reviews.

**Bring a compatible model endpoint. Run the coordinator on your infrastructure.
Keep your policies, evidence and approval decisions under your control.**

Built for maintainers automating PR review, teams that need auditable AI workflows,
and researchers testing how an agent's harness can improve over time.

## Why Harness4?

| What you want | What Harness4 gives you |
|---|---|
| **Follow through on a review** | A GitHub review → bounded repair → fresh review → CI → approval workflow. |
| **Learn from recurring mistakes** | Verified feedback becomes a candidate checklist, evaluated on separate target and regression cohorts. |
| **Control what changes** | Explicit write grants, protected paths, a separate approval account and human approval of learned policies. |
| **Understand what happened** | Commit-pinned reports, policy versions, durable write receipts and an auditable learning history. |
| **Recover when something goes wrong** | Evidence-based reconciliation of uncertain writes, policy rollback and revocation after feedback corrections. |
| **Choose your model** | An explicit Chat Completions-compatible endpoint, including local endpoints that satisfy the adapter contract. |

## Quickstart

**Python 3.11+ and Git.** Install from this repository; Harness4 is not yet published
to PyPI. These commands use a macOS/Linux shell:

```sh
git clone https://github.com/YangZhongqiHealth/harness4.git
cd harness4
python -m venv .venv
source .venv/bin/activate
python -m pip install .

# Run the complete learning lifecycle. No API key or GitHub token needed.
python examples/learning_demo.py
```

The demo creates temporary state, learns a candidate checklist, evaluates it,
activates it and rolls it back. Selected fields from its JSON output:

```json
{
  "evidence_class": "scripted_demo",
  "quality_claim": false,
  "decision": "eligible",
  "fresh_review_finding_count": 1,
  "rollback_review_finding_count": 0,
  "generation": 2
}
```

In this fixture, the new checklist catches a missing-value bug; rolling back restores
the original behavior. The demo uses scripted model replies and real persistence,
activation and rollback. It demonstrates the lifecycle, not real-model accuracy.

To keep the demo's audit history, use a **new directory**:

```sh
h4 learning demo --state-dir /tmp/harness4-learning-demo
h4 learning status --state-dir /tmp/harness4-learning-demo
```

## Choose your first run

Start with the outcome you want. Each arrow below is a setup dependency; learning
is optional, and remote writes always need their own authorization.

```mermaid
flowchart LR
    Install["Install Harness4"] --> Demo["Run demo<br/>No credentials"]
    Install --> Local["Inspect local diff<br/>Read-only report"]
    Install --> Setup["Configure model,<br/>GitHub + policy"]
    Setup --> Observe["Observe a PR<br/>No remote writes"]
    Observe --> Writes["Opt into writes<br/>Repairs / approval"]
    Setup --> Capture["Initialize learning<br/>Record review episodes"]
    Capture --> Learn["Verify feedback<br/>Follow learning loop"]
    classDef start fill:#eff6ff,stroke:#2563eb,color:#172554
    classDef optional fill:#f0fdf4,stroke:#16a34a,color:#14532d
    class Install,Demo,Local,Setup,Observe,Writes start
    class Capture,Learn optional
```

| Your goal | Start here | What you get |
|---|---|---|
| **Understand the whole loop** | `python examples/learning_demo.py` | A scripted demonstration with real activation and rollback; no credentials. |
| **Inspect a local change** | `h4 ship --repo . --base HEAD~1 --head HEAD` | JSON policy report; add model settings for AI review. |
| **Review a GitHub PR** | [`h4 ship-github`](docs/GITHUB_WORKFLOW.md) | Two review passes and actual CI evidence; observation by default. |
| **Enable remote actions** | Configure grants, then add `--write`; separately configure `--approve` | Bounded repairs and policy-gated approval; no merge. |
| **Improve future reviews** | [`h4 learning init`](docs/LEARNING.md), then `ship-github --learning-dir …` | Recorded episodes for verified feedback and a separate evaluation cycle. |

For learning, the command sequence is `feedback` → `dataset` → `run --live` →
`inspect` → `approve` → `promote`. Each command takes explicit IDs and settings;
use the [complete walkthrough](docs/LEARNING.md) rather than treating this sequence
as a shell command. If evaluation rejects or abstains, keep the current policy.
Use `rollback` to restore a prior version, or `retract` to correct bad evidence.

## How it works

Two connected loops: one handles a pull request; the other evaluates changes to the
review guidance used on future pull requests.

```mermaid
flowchart LR
    PR["Pull request"] --> Review["Review pinned code<br/>Two model passes"]
    Review -->|Findings| Repair["Bounded repair<br/>Allowed files only"]
    Repair -->|New commit| Review
    Review -->|No findings| Gate["GitHub CI<br/>+ trusted policy"]
    Gate -->|Checks pass| Approve["Approval<br/>Separate account"]
    Gate -->|Blocked or uncertain| Human["Human review"]
    Repair -->|Budget exhausted| Human
    classDef work fill:#eff6ff,stroke:#2563eb,color:#172554
    classDef control fill:#f0fdf4,stroke:#16a34a,color:#14532d
    classDef stop fill:#fff7ed,stroke:#ea580c,color:#7c2d12
    class PR,Review,Repair work
    class Gate,Approve control
    class Human stop
```

Remote writes require explicit opt-in and trusted policy grants. Approval requires
passing checks on the reviewed commit, a separate GitHub user and branch protection.
The coordinator does not execute PR code or merge PRs. See the
[GitHub workflow guide](docs/GITHUB_WORKFLOW.md) for setup and recovery.

### Start with a local review

Inside the cloned repository, inspect the latest committed change without credentials:

```sh
h4 ship --repo . --base HEAD~1 --head HEAD
```

This produces a structured policy report without calling a model. To review another
repository with a model, configure `H4_MODEL_KEY` in your environment, then run:

```sh
h4 ship --repo /path/to/your/repo --base HEAD~1 --head HEAD \
  --model YOUR_MODEL --base-url https://YOUR_PROVIDER/v1 \
  --policy examples/ship-policy.json --checks unknown
```

Only committed changes are reviewed. Model calls send the diff to your configured
endpoint and may incur charges. Local recommendations are advisory; the local
command's exit code is not a merge gate. [Local review reference →](docs/LOCAL_REVIEW.md)

### Connect a GitHub repository

Configure your repository policy, model credential and GitHub token using the
[setup guide](docs/GITHUB_WORKFLOW.md), then start in observation mode:

```sh
h4 ship-github --policy /trusted/project-policy.json --pr 42 \
  --state-dir /trusted/state/github \
  --model YOUR_MODEL --base-url https://YOUR_PROVIDER/v1
```

Add `--write` to allow policy-permitted review posts and repairs. Add `--approve`
only after configuring the separate approval credential and branch protection.
To use an approved learned checklist and record feedback episodes, add
`--learning-dir /trusted/state/learning` after [initializing learning](docs/LEARNING.md).

## A learning loop you can audit

A useful lesson needs evidence before it becomes the next review policy.

```mermaid
flowchart LR
    Evidence["Verified<br/>feedback"] --> Dev["Propose + select<br/>Development data"]
    Dev --> Eval["Evaluate<br/>Fresh release data"]
    Eval -->|Pass| Approve["Operator<br/>approval"]
    Eval -->|Fail or uncertain| Stop["Keep current<br/>policy"]
    Approve --> Active["Activate<br/>Future reviews"]
    Active -->|Rollback| Previous["Restore prior<br/>version"]
    Active -.->|New evidence| Evidence
    classDef data fill:#eff6ff,stroke:#2563eb,color:#172554
    classDef gate fill:#f0fdf4,stroke:#16a34a,color:#14532d
    classDef hold fill:#fff7ed,stroke:#ea580c,color:#7c2d12
    class Evidence,Dev data
    class Eval,Approve,Active gate
    class Stop,Previous hold
```

- **Separate development from release evidence.** The proposer sees development
  labels; the release cohort is consumed once, including after a crash.
- **Check improvement and retention.** Paired evaluations compare candidate and
  current policy. Confidence bounds and regression checks can reject or abstain.
- **Approve the exact version.** Activation checks the persisted report, policy
  generation, evidence validity, expiry and a one-use approval.
- **Reverse a decision.** Roll back an active policy, or retract incorrect feedback
  to invalidate dependent policies. The original baseline remains available.

The learnable surface today is the **review checklist**. Model weights, GitHub
permissions, execution code and evaluation rules stay fixed. Production learning
requires explicit inference budgets and independent, verified data; the default
gate requires at least 100 target and 100 regression source groups.

[Run a real learning cycle →](docs/LEARNING.md) ·
[Research and design decisions →](docs/research/2026-11-25-learning.md)

## What “4” stands for

Our Harness 4.0 direction is an agent workflow that can **learn from verified
experience, evaluate a change, and adopt or reverse it under explicit control**.
The current release implements that direction for PR review guidance. “4” names the
project's architectural ambition; the package is currently **0.6.0a0, an alpha**.

We are building an open-source alternative for the PR workflow introduced by
[Claude Ship](https://claude.com/resources/articles/introducing-claude-ship), with
model choice and an inspectable learning lifecycle as central design goals.
Harness4 is independent of Anthropic. Feature parity and superior review quality
remain goals to validate, not benchmark results we claim.

## Harness4 and Claude Ship

**Our extension of the PR workflow: own the engine, choose the model, and control
how review guidance learns.** Harness4 implements three concrete capabilities
central to this direction:

1. **An open, self-hosted engine.** Inspect, modify and redistribute the coordinator
   under MIT. Keep its state and policies on infrastructure you operate.
2. **A replaceable model endpoint.** Select a compatible hosted or local deployment.
   Model behavior still needs qualification; endpoint choice is not a quality guarantee.
3. **A governed learning lifecycle.** Propose checklist changes from verified feedback,
   evaluate on fresh target and regression data, explicitly approve a version, and
   roll it back or revoke its evidence dependencies.

The comparison below separates shipped Harness4 capabilities from what Anthropic
publicly documents. Checked **2026-11-25** against its
[announcement][ship-announcement], [product page][ship-product] and
[documentation][ship-docs]. “Not described” means absent from those reviewed pages,
not proof that Anthropic lacks an internal capability.

| Dimension | Claude Ship — official description | Harness4 — current alpha |
|---|---|---|
| PR lifecycle | Code Review, PR Steward and Claude Approvals coordinate reviews, fixes and policy decisions. [Source][ship-docs] | Two review passes, bounded text repairs, fresh CI checks and separate-account approval. |
| Ownership and deployment | Claude organization setup; the reviewed pages do not describe a self-hostable MIT engine. [Source][ship-docs] | MIT source; run and modify the coordinator yourself. Model requests go to your chosen endpoint. |
| Model choice | Claude-based workflow; interchangeable model endpoints are not offered in the reviewed pages. [Source][ship-product] | Explicit Chat Completions-compatible endpoint, with a pinned profile for learning. |
| Improving review guidance | `REVIEW.md` customization; the reviewed pages do not describe a held-out learning/promotion/rollback lifecycle. [Source][ship-product] | Verified labels, dev-only proposals, one-use release cohorts, approval, rollback and evidence retraction. |
| CI failures, conflicts and feedback | Steward handles failing checks, merge conflicts and feedback from humans and review tools. [Source][ship-announcement] | Repairs findings from its own review; CI failures, conflicts and external review feedback need human handling today. |
| Adoption and cost | Team/Enterprise service with token billing; `/ship` is also available in Claude Code. [Source][ship-announcement] | Install the repository and configure tokens/policy yourself. MIT code; infrastructure and model usage can cost money. |

**Choose Harness4 when open ownership, endpoint choice and inspectable learning
controls matter enough to operate an early-stage tool.** Claude Ship currently
documents broader PR stewardship and integrated onboarding. We have not run a
cost-matched head-to-head benchmark, so we claim neither better accuracy nor lower
cost. Our “upgrade” is the implemented architecture and control surface; proving
better engineering outcomes is the next step.

[ship-announcement]: https://claude.com/resources/articles/introducing-claude-ship
[ship-product]: https://claude.com/product/claude-ship
[ship-docs]: https://code.claude.com/docs/en/claude-ship

## Built today, measured honestly

**289 automated tests** cover contracts, provider behavior, persistence, GitHub
orchestration and learning. CI checks Python 3.11–3.13, runs credential-free examples
and builds the package. A synthetic integration exercises 809 mocked model requests,
policy activation, GitHub review, rollback and restart deduplication.

| Available in this alpha | Next milestones |
|---|---|
| Local review and the opt-in GitHub lifecycle | Live provider and real-PR qualification |
| Verified-feedback learning, evaluation and rollback | Public, independently labeled quality benchmarks |
| Private local state and durable write reconciliation | GitHub App installation and webhooks |
| Same-repository text PRs and classic branch protection | Fork support, isolated CI-failure and conflict repair |

These tests establish implementation behavior. Live quality gains have not yet been
measured. The coordinator trusts its local OS owner; model/learner separation is not
an OS sandbox. [Validation evidence](tests/VALIDATION.md) · [Current status](planning/STATUS.md)

## Documentation

| Start here | Go deeper |
|---|---|
| [Local review](docs/LOCAL_REVIEW.md) | [Model gateway and conformance](docs/PROVIDERS.md) |
| [GitHub setup and recovery](docs/GITHUB_WORKFLOW.md) | [Persistence and recovery semantics](docs/PERSISTENCE.md) |
| [Learning, approval and rollback](docs/LEARNING.md) | [Learning research](docs/research/2026-11-25-learning.md) |
| [Read-only GitHub Actions example](examples/ship-observe.yml) | [Architecture](docs/DESIGN.md) · [Product acceptance plan](planning/PRODUCT.md) |

## Build with us

Help make evidence-based PR automation useful in real repositories. Especially
valuable contributions: reproducible provider compatibility reports, independently
verified review cases, failure/recovery tests, and onboarding improvements.

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
```

[Open an issue](https://github.com/YangZhongqiHealth/harness4/issues) with a reproducible
problem or proposed contribution. Read [CONTRIBUTING.md](CONTRIBUTING.md) before a PR
and [SECURITY.md](SECURITY.md) for sensitive reports. Please remove credentials and
private source from examples. If this direction matters to you, star the repository
and help us test it against real engineering work.

[MIT licensed](LICENSE). Your infrastructure. Your model endpoint. Your review policy.
