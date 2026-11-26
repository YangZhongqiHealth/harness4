<div align="center">

# Harness4

### An open-source alternative to Claude Ship—with a verifiable self-improvement loop.

Review pull requests. Repair findings. Apply your approval policy.<br>
Improve future reviews through evaluated feedback, explicit approval and rollback.

**Your models. Your infrastructure. Your control.**

[![CI](https://github.com/YangZhongqiHealth/harness4/actions/workflows/ci.yml/badge.svg)](https://github.com/YangZhongqiHealth/harness4/actions/workflows/ci.yml)
[![MIT](https://img.shields.io/badge/license-MIT-22c55e)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776ab)](pyproject.toml)
[![Alpha](https://img.shields.io/badge/status-alpha-f59e0b)](planning/STATUS.md)

[Try the demo](#quickstart) · [How it works](#how-it-works) · [Use your own repo](#use-it-on-your-repository) · [Compare Claude Ship](#harness4-and-claude-ship) · [Contribute](#build-with-us)

</div>

Harness4 is for maintainers who want to **run, inspect and extend their PR automation**.
It coordinates review, bounded repairs, CI checks and optional approval using a
compatible hosted or local model endpoint.

It also gives verified review feedback a path into future reviews. A proposed
checklist must pass fresh evaluation and regression gates before you can approve
and activate it. Each release is versioned and reversible.

**Public alpha:** the workflow and learning lifecycle are implemented and tested with
simulated services. Live PR qualification and measured learning gains are still ahead.
[What works today →](#project-status)

## Why Harness4?

| What you want | What Harness4 gives you |
|---|---|
| Own the engine | MIT source and a coordinator you run on your infrastructure. |
| Choose the model | A Chat Completions-compatible endpoint, with review guidance separate from the provider. |
| Learn from review mistakes | Verified feedback → candidate checklist → fresh evaluation → approved release. |
| Control consequential actions | Operator-owned policy, explicit write grants, separate approval credentials and no merge operation. |
| Inspect and recover | Persistent write records, evidence-based reconciliation and versioned checklist rollback. |

The **Harness 4.0** idea is a review workflow that can improve its guidance through
measured, reversible changes. Today, the learnable surface is the **review checklist**;
model weights, permissions and evaluation rules stay fixed.

## How it works

![Two connected loops: review and repair a pinned PR, check CI and policy, then optionally approve; separately, verified feedback produces a candidate checklist that must pass fresh evaluation and human approval before use in future reviews. Rollback restores a prior checklist.](docs/assets/harness4-loop.svg)

**For each PR:** review a pinned revision → repair within policy → review the new
revision → check GitHub CI → optionally approve with a separate account. Blocked
checks, exhausted budgets and uncertain evidence return control to a person.
Harness4 never merges the PR.

**Between reviews:** curate verified feedback → propose a checklist → evaluate it
against the current version → approve and activate, or keep the current version.
Learning runs when you request it. [Detailed workflow diagrams →](docs/WORKFLOWS.md)

## Quickstart

**Try the learning loop without API keys, GitHub credentials or remote writes.**
Requires Python 3.11+ and Git; commands below use a macOS/Linux shell.

```sh
git clone https://github.com/YangZhongqiHealth/harness4.git
cd harness4
python -m venv .venv
source .venv/bin/activate
python -m pip install .
python examples/learning_demo.py
```

The demo evaluates a candidate checklist, approves and activates it, runs a fresh
review, then rolls back. Selected fields from its JSON output:

```json
{
  "evidence_class": "scripted_demo",
  "quality_claim": false,
  "decision": "eligible",
  "fresh_review_finding_count": 1,
  "rollback_review_finding_count": 0
}
```

**The visible result:** the activated checklist catches the fixture's missing-value
bug; rollback restores the original behavior. Model replies are scripted, while
storage, evaluation gates, approval, activation and rollback use the real lifecycle.
The demo verifies the mechanism; it does not measure live model improvement.

Install from this checkout; there is no PyPI release yet.
[Windows and local setup →](docs/LOCAL_REVIEW.md)

## What self-improvement looks like

Consider a function where `None` means “measurement unavailable”:

```python
return value or 0  # Silently turns a missing measurement into a real zero.
```

A review misses the bug. A maintainer verifies the mistake against that revision.
That feedback becomes development evidence for a candidate rule:

> Check whether defaulting with `or` collapses a meaningful missing value into a valid value.

The proposed rule does **not** go straight into future reviews:

| Step | What happens | What can stop it |
|---|---|---|
| Verify | Attach human- or deterministically verified labels to the recorded revision. | Unverified feedback cannot serve as verified learning evidence. |
| Propose | Use development examples to create a bounded checklist change. | The proposer cannot change execution permissions or the evaluator. |
| Evaluate | Compare candidate and current checklist on fresh target and regression cases. | Insufficient evidence, missed gates or regressions block eligibility. |
| Release | Inspect the report, approve the exact version, then activate it. | Passing evaluation alone does not activate a candidate. |
| Recover | Roll back a checklist or retract incorrect feedback. | Retraction revokes dependent policies and restores baseline when needed. |

This example illustrates the intended learning process. The quickstart demonstrates
it with scripted replies. Production defaults require at least **100 target and
100 regression source groups**, with release cohorts used once and release labels
kept out of model prompts. One successful example is not enough.

[Run the learning workflow](docs/LEARNING.md) ·
[Evaluation design and research](docs/research/2026-11-25-learning.md)

## Use it on your repository

Start with a read-only review. Enable repairs, approval and learning independently
as you qualify them for your repository.

### Review a local change

Set `H4_MODEL_KEY` through your environment or secret manager, then run:

```sh
h4 ship --repo /path/to/your/repo --base HEAD~1 --head HEAD \
  --model YOUR_MODEL --base-url https://YOUR_PROVIDER/v1
```

You get a structured review of **committed changes**, without modifying the repository.
Omit `--model` and `--base-url` for a credential-free policy report instead of AI review.
Model calls send code to the selected endpoint and may incur charges.
[Local review reference →](docs/LOCAL_REVIEW.md)

### Review a GitHub PR, then opt into writes

Follow the [GitHub setup guide](docs/GITHUB_WORKFLOW.md) to create an operator-owned
policy and configure `H4_GITHUB_TOKEN` and `H4_MODEL_KEY`:

```sh
h4 ship-github --policy /trusted/project-policy.json --pr 42 \
  --state-dir /trusted/state/github \
  --model YOUR_MODEL --base-url https://YOUR_PROVIDER/v1
```

| Mode | How to enable it | Result |
|---|---|---|
| Observe | Command above | Review and report; no GitHub writes. |
| Review + repair | Add `--write`, with matching policy grants | Post reviews and make bounded repair commits, then review again. |
| Approval | Also add `--approve`, configure a separate user credential and required branch protection | Approve only when review, CI and policy gates pass. |
| Learned guidance | Initialize a learning store, then add `--learning-dir /trusted/state/learning` | Pin the active checklist and record review episodes. |

Use separate directories for learning state and the write journal. Recording episodes
does not start training: curate verified labels and explicitly run evaluation,
approval and promotion through [`h4 learning`](docs/LEARNING.md).

## Harness4 and Claude Ship

**Think of Harness4 as an open-source Claude Ship alternative with an explicit
self-improvement lifecycle.** The shared goal is moving PRs through review, fixes
and an approval decision. The added design focus is ownership, model choice and
control over how review guidance evolves.

| Dimension | Harness4 today | Claude Ship, as documented |
|---|---|---|
| Operate and extend | Self-hosted MIT coordinator | Organization service on Team/Enterprise. [Docs][ship-docs] |
| Model choice | Compatible hosted or local endpoint | Claude-based workflow. [Product][ship-product] |
| Evolve review guidance | Verified feedback, fresh evaluation, explicit release and rollback | `REVIEW.md` customization; the reviewed pages do not describe this learning-release lifecycle. [Product][ship-product] |
| Fix PR problems | Bounded fixes from its own findings; CI failures and conflicts escalate | Repairs failing checks, merge conflicts and human/tool review feedback. [Docs][ship-docs] |
| Get started | CLI, operator policy and credentials | Integrated organization setup. [Docs][ship-docs] |

**Choose Harness4** if you want to own and extend the engine or experiment with
review learning. **Claude Ship currently documents broader PR stewardship and
integrated onboarding.** Harness4 is not yet a feature-complete replacement, and
no head-to-head accuracy or cost advantage has been measured.

Sources checked **2026-11-26**. “Not described” refers to public documentation, not
Anthropic's internal systems. Harness4 is independent and unaffiliated with Anthropic.
[Detailed comparison →](docs/COMPARISON.md)

[ship-docs]: https://code.claude.com/docs/en/claude-ship
[ship-product]: https://claude.com/product/claude-ship

## Project status

**0.6.0a0 · Alpha · 289 automated tests · CI on Python 3.11–3.13**

| Available now | Next milestones |
|---|---|
| Local review and opt-in GitHub review → repair → approval | Live-provider and real-PR qualification |
| Durable write records and reconciliation | GitHub App onboarding and webhooks |
| Checklist proposal, evaluation, activation and rollback | Independently labeled quality and learning benchmarks |
| Revision-bound feedback and dependent-policy revocation | Independent finding verification and isolated CI/conflict repair |

Tests use simulated GitHub/model responses and real SQLite storage, including crash
and recovery cases. Current GitHub support covers same-repository text PRs and classic
branch protection. The coordinator does not execute PR code; testing runs in your
separately configured CI. It trusts its local OS owner and is not an execution sandbox.

[Validation evidence](tests/VALIDATION.md) · [Implementation status](planning/STATUS.md) ·
[Product roadmap](planning/PRODUCT.md)

## Build with us

Help turn the tested alpha into a qualified tool for real repositories:

- **Test a provider:** report reproducible compatibility results and failure cases.
- **Improve the evidence:** contribute independently verified review cases, with permission to share the code.
- **Strengthen recovery:** add cases for interrupted writes, stale PRs and incorrect feedback.

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
```

Keep ordinary tests credential-free and shared examples free of secrets and private code.
[Open an issue](https://github.com/YangZhongqiHealth/harness4/issues) ·
[Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [MIT license](LICENSE)

## Documentation

- **Use:** [Local review](docs/LOCAL_REVIEW.md) · [GitHub setup and recovery](docs/GITHUB_WORKFLOW.md) · [Learning](docs/LEARNING.md)
- **Understand:** [Workflow diagrams](docs/WORKFLOWS.md) · [Architecture](docs/DESIGN.md) · [Learning research](docs/research/2026-11-25-learning.md)
- **Integrate:** [Provider contract](docs/PROVIDERS.md) · [Persistence](docs/PERSISTENCE.md) · [Read-only Actions example](examples/ship-observe.yml)
