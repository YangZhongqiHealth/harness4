# Verifiable, reversible review learning

Harness4 0.6 adds an operator-controlled learning loop to `ship-github`. It learns
**one review checklist**, using the configured model without changing its weights.
It persists evidence, searches on development cases, evaluates one candidate on a
fresh release cohort, and requires explicit approval before activation. GitHub
permissions, repair constraints, CI gates and the evaluator remain operator-owned.

This is a bounded implementation of the Harness4 learning direction, not a claim
of SOTA performance or full autonomous software evolution. Read the
[primary-source research and design synthesis](research/2026-11-25-learning.md).

## Try the entire lifecycle without credentials

```sh
h4 learning demo --state-dir /tmp/harness4-learning-demo
```

Use a new directory. The command collects scripted evidence, proposes a checklist,
evaluates it, approves and activates it, reviews with it, and rolls it back. Output
includes `quality_claim: false`, `evidence_class: scripted_demo`, the version hashes
and finding counts before/after rollback. This exercises real persistence and pointer
changes. Its small fixture gate is restricted to demo scope; `ship-github` refuses
that scope. It demonstrates mechanics, not improved real-model accuracy.

## Production setup and evidence collection

1. Choose a stable, preferably immutable model deployment. Copy
   [the profile](../examples/learning-profile.json) and replace both the request
   model and expected response revision. The response `model` must exactly match
   `revision`. The endpoint, engine, fixed instructions and output/time limits are
   part of the profile hash. A provider alias alone cannot prove stable weights.
2. Initialize a private learning directory, separate from the GitHub write journal:

```sh
h4 learning init --state-dir /trusted/state/learning \
  --repository owner/project --profile /trusted/learning-profile.json
h4 ship-github --policy /trusted/project-policy.json --pr 42 \
  --state-dir /trusted/state/github --learning-dir /trusted/state/learning \
  --model YOUR_PINNED_MODEL --base-url https://YOUR_PROVIDER/v1
```

Configure `H4_MODEL_KEY` and the GitHub credential as described in the
[GitHub guide](GITHUB_WORKFLOW.md). Match the profile's model, endpoint, timeout and
output limit exactly. This command observes by default; normal write/approval grants
remain necessary for remote mutations. `--learning-dir` opts into retaining private
source snapshots and model outputs and using the active checklist. Without it,
existing review behavior is unchanged. The local `ship` command does not use learning.

Each review report includes `learning_episode`, `review_policy_hash` and the exact
PR head. The episode stores the source input, both review outputs and profile hash.
After independent verification, provide the complete expected finding set in a file:

```json
{"labels": [{"path": "src/app.py", "line": 12, "severity": "high"}]}
```

Use `{"labels": []}` only for a verified clean case. Severity is `critical`, `high`,
`medium` or `low`. Labels identify findings in the recorded revision, not today's
working tree. A passing CI check alone does not establish a complete finding set.

```sh
h4 learning feedback --state-dir /trusted/state/learning \
  --episode EPISODE_HASH --labels /trusted/labels.json \
  --group project-pr-42 --source human_verified \
  --source-ref 'review record or test evidence reference' --consent
```

`deterministic_verified` is also accepted when a trusted test establishes the label.
The source flag is an operator attestation, not an automated authenticity check.
The local OS identity is recorded. A model's self-critique is not independent feedback.
Do not submit secrets or source you cannot send to the configured provider.

## Freeze data, then run a bounded experiment

Create a manifest containing returned feedback hashes:

```json
{
  "name": "project-review-cohort-001",
  "cases": [
    {"feedback_id": "DEVELOPMENT_HASH", "split": "dev"},
    {"feedback_id": "TARGET_HASH", "split": "target"},
    {"feedback_id": "ANCHOR_HASH", "split": "anchor"}
  ]
}
```

The three-row snippet illustrates the format; it is insufficient for the production
gate. Defaults require **at least 100 target and 100 anchor source groups**, plus
useful development cases. Group related revisions/variants under the same group.
Do not create fictional independence by assigning each row a different name.
Software rejects repeated input hashes and groups crossing splits, but cannot prove
sampling independence or detect all semantic duplicates and model contamination.

Development data should contain verified failures and correct behavior to retain.
Target data represents the intended improvement distribution; anchors represent
existing behavior that must remain correct. Freeze the split and protocol before
search. The learner sees only development labels and traces. Release labels, group
IDs and split names never enter model review requests.

```sh
h4 learning dataset --state-dir /trusted/state/learning --manifest /trusted/cohort.json
h4 learning run --state-dir /trusted/state/learning --dataset DATASET_HASH \
  --protocol examples/learning-protocol.json --live
```

`--live` explicitly enables inference, potentially with provider charges. The example
protocol permits one candidate and 1,000 calls. The worst-case plan is
`2 * dev_cases * (1 + max_candidates) + max_candidates + 4 * release_cases`.
Two development cases and 200 release cases with one candidate require 809 calls.
Insufficient group counts or call budget stop before inference. Each review uses two
passes. Attempts, including failed requests, consume the call allowance; there are
no automatic retries. Wall time and per-call output tokens are bounded.

`max_total_tokens` can optionally bound reported input plus output usage; unknown
usage then blocks release. Admission uses a conservative byte estimate, with actual
usage checked after each call. Provider tokenization/overbilling cannot be prevented
by this client; use provider-side spending limits for monetary caps. Without a total
cap, unknown usage remains unknown in the report, never zero-cost evidence.

Every attempt retains an archive and durable report, including invalid proposals and
inconclusive results. The model can replace only `review_checklist` (8,000 characters
maximum). It cannot grant tools, change CI requirements, edit the evaluator or approve
itself. A candidate must improve development exact-match accuracy without observed
development regressions before the release evaluator sees it.

## What passes the release gate

The metric compares the union of two review passes with the verified set of
`(path, line, severity)` labels. Exact matching penalizes missing and extra findings;
it is a deliberately narrow metric, not semantic proof of a defect or fix.

The evaluator runs both incumbent and candidate afresh, with the same pinned model
and pipeline. It averages paired accuracy differences within source groups. It
requires a positive lower confidence bound on target gain, zero observed anchor
regressions and an upper bound on anchor regression risk. Defaults use 95% joint
per-cycle confidence, a minimum gain of 0.02 and maximum anchor risk of 0.05.
See the research report for formulas and assumptions. These conservative bounds may
need far more than 100 groups for modest improvements. `inconclusive` is expected
when evidence is weak; it never activates a policy.

Release groups and input hashes are durably consumed **before any release call**.
A crash, failure or rejection does not permit reuse, even under a renamed dataset.
A retry currently may spend development calls before detecting a consumed release
cohort; supply a fresh cohort instead. Never delete the store to reset this rule.
Repeated cycles need fresh independent cohorts; the bounds are not a lifetime
multiple-testing guarantee.

## Review, approve, activate, and roll back

```sh
h4 learning inspect --state-dir /trusted/state/learning --id REPORT_HASH
h4 learning inspect --state-dir /trusted/state/learning --kind policy --id CANDIDATE_HASH
h4 learning approve --state-dir /trusted/state/learning --report REPORT_HASH
h4 learning promote --state-dir /trusted/state/learning --approval APPROVAL_ID
h4 learning status --state-dir /trusted/state/learning
```

Inspect the candidate text, development archive, release metrics and usage before
approval. An eligible report does not activate anything by itself. Activation is a
transaction: exact report receipt, parent, profile, scope, generation, evidence epoch,
expiry and one-use approval must still match. An intervening activation/rollback
invalidates old approvals, even if the pointer returns to the same policy hash.
Subsequent `ship-github --learning-dir ...` runs pin the new policy at startup;
the policy hash also participates in GitHub effect identities.

```sh
h4 learning rollback --state-dir /trusted/state/learning \
  --target PREVIOUSLY_ACTIVE_HASH --expected-generation CURRENT_GENERATION \
  --reason 'Observed a regression'
h4 learning retract --state-dir /trusted/state/learning \
  --feedback INCORRECT_FEEDBACK_HASH --reason 'Independent verification corrected this label'
```

Rollback restores a compatible, non-revoked policy that was previously active.
It affects future reviews, not already posted reviews or repair commits. Retraction
invalidates dependent candidates and their descendants, invalidates pending approvals,
and restores baseline if the active policy is affected. Submit corrected feedback
only after retracting the old record; consumed cohorts stay consumed.

## Operational boundary

This alpha uses a trusted local coordinator and OS-owner-controlled store. Files are
private and content-addressed; SQLite uses full synchronous transactions and a local
process lock. The model receives text, no tools or store handle. This is logical
separation from the proposer, not an OS sandbox against malicious Python running as
the same user. Do not expose raw store access to untrusted plugins or PR code.

The learning lock is held throughout evaluation and throughout an opted-in GitHub
run. Concurrent promotion/retraction is rejected; stop the running coordinator first
for an emergency change. Interrupted experiments remain unapprovable. Use a persistent
private volume and preserve the database and audit history across restarts. Distributed
workers, cross-store deduplication and remote approval identities are not implemented.

There is no silent background training, automatic activation, weight training or
unrestricted self-editing. No live quality improvement has yet been measured. The
HTTP/SQLite integration tests use synthetic model and GitHub responses, including a
202-case production-gate fixture; they establish implementation behavior only.
