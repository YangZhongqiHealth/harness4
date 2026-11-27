# GitHub review → repair → approval (alpha)

`h4 ship-github` runs the GitHub lifecycle from a trusted operator machine. It reads
an open PR, reviews its diff and full changed-file contents twice, posts a review,
proposes bounded text replacements, creates a repair commit, reviews the new head,
waits for required GitHub checks, and optionally approves. It never merges.

This is a working bounded implementation, tested with the real HTTP adapter and
SQLite journal against a simulated GitHub service. Live model + GitHub lifecycle
qualification is still pending. It is not a complete Claude Ship replacement yet.

## Configure once

Install Harness4 using the repository README. Put the installed package, policy and
persistent state outside the PR checkout. Run only trusted Harness4 code.

Copy `examples/github-policy.json` into an operator-owned location, for example
`/opt/harness4/policies/project.json`, and replace:

- `repository`: the exact `owner/repository` that Harness4 may access.
- `base_branch`: the allowed destination branch.
- `required_checks`: exact check-run names and the producing GitHub App IDs. Every
  listed check must finish with `success` on the reviewed head. Missing checks,
  skipped/neutral results, another App's check and another commit's check do not pass.
- `repair_prefixes`: directories Harness4 may edit, within files already changed by
  the PR. The example protects tests as well as workflows/security/auth code.
- `allow_repair` and `allow_approval`: start false; enable only the capabilities you
  want. CLI write flags are also required. PR contents cannot override these grants.

Use GitHub's check-run API to identify names and App IDs; the example's ID `1` is a
placeholder, not an actual recommendation. A read-only query with an authenticated
GitHub CLI is:

```sh
gh api repos/OWNER/REPO/commits/PR_HEAD_SHA/check-runs \
  --jq '.check_runs[] | {name, app_id: .app.id, head_sha}'
```

Set credentials through your secret manager or environment:

- `H4_MODEL_KEY`: the selected model provider's key.
- `H4_GITHUB_TOKEN`: a fine-grained user token scoped to this repository. Reading
  needs Contents, Pull requests and Checks read access. `--write` additionally needs
  Contents and Pull requests write access. Approval preflight reads classic branch
  protection, which requires Administration read access.
- `H4_APPROVAL_TOKEN`: a **different GitHub user's** repository-scoped token with
  Pull requests write access, permission to submit/dismiss reviews, and relevant
  read access. This user must not be the PR author. Only needed for approval.

The current CLI uses user tokens (`GET /user`); installation-token GitHub Apps are
not yet supported. `gh auth login` alone does not populate these environment variables.
You can select other variable names with `--key-env`, `--github-key-env` and
`--approval-key-env`. Never pass token values as command-line options.

For automated approval, classic base-branch protection must enable stale approval
dismissal, approval of the most recent push, and strict required checks. Each
branch-required check must have an explicit App ID and also appear in the trusted
policy. Ruleset-only repositories currently fail closed. Harness4 does not modify
these settings, bypass protection, satisfy CODEOWNERS on your behalf, or merge.

Configure CI separately to run untrusted PR code in an isolated, disposable runner
without model keys, approval tokens, production secrets or write credentials.
The coordinator only reads results; it cannot establish that an arbitrary CI job
is securely isolated. Keep the validation workflow and policy under trusted control.
Avoid the default Actions `GITHUB_TOKEN` for the writer: its pushes normally do not
trigger another workflow run. The user-token deployment is intended to trigger CI
for repair commits.

## Use it

Start with read-only GitHub observation (this still calls the model and may cost money):

```sh
h4 ship-github --policy /opt/harness4/policies/project.json --pr 42 \
  --state-dir "$HOME/.local/state/harness4/project" \
  --model YOUR_MODEL --base-url https://YOUR_PROVIDER/v1
```

After enabling `allow_repair`, add `--write` to post reviews and repair findings.
After enabling `allow_approval` and configuring the separate approver/protection,
run the complete loop:

```sh
h4 ship-github --policy /opt/harness4/policies/project.json --pr 42 \
  --state-dir "$HOME/.local/state/harness4/project" \
  --model YOUR_MODEL --base-url https://YOUR_PROVIDER/v1 \
  --write --approve --check-polls 20 --poll-seconds 15
```

Example progression: PR #42 contains `value = 1`, where review finds a defect.
Harness4 posts findings against head A, proposes the exact replacement `value = 2`,
and creates commit B with A as its only parent. It updates the PR branch without
force, reviews B twice, waits for the configured checks on B, then approves B with
the separate account. If checks are still running, it returns `waiting_checks`.
Rerun the same command and state directory after CI completes. The journal prevents
repeating successful review posts, repair effects and approvals for the same head,
base and policy. Re-reviewing can incur new model calls.

JSON statuses:

| Status | Meaning | Exit |
|---|---|---|
| `eligible` | Clean reviews and passing configured checks; no approval requested | 0 |
| `approved` | GitHub accepted the pinned approval and post-write checks passed | 0 |
| `reconciled` | Explicit read-only recovery completed; run the normal command next | 0 |
| `waiting_checks` | Required checks are missing or still running; resume later | 3 |
| `needs_human` | Findings, failed checks, merge conflict/unknown mergeability, or exhausted repair budget | 3 |
| `blocked` | Scope, authorization, freshness, transport or recovery condition prevented completion | 3 |
| Input/provider error | Invalid configuration or unusable model response | 2 |

These exit codes are not a merge authorization. GitHub branch protection remains
the merge gate. `approved` describes the checked revision at that instant.

## Limits and recovery

Default limits are 20 changed files, 500 changed lines, 200 KB of serialized review
context and two repair rounds per PR journal. With two repairs, a run makes at most
eight model calls, each with the configured output-token ceiling (default 4,096)
and deadline (default 60 seconds). API responses are capped at 2 MB, pagination at
1,000 records, individual API requests at 30 seconds, and CI polls at 40. Unknown
model usage remains unknown. These are operation/token bounds, not currency budgets.

Only same-repository, non-draft PRs with added/modified UTF-8 text files are supported.
Forks, deleted/renamed files, binary/missing patches and protected paths require
human handling. `.github/` and `.git/` cannot be reviewed automatically even if the
policy omits them. Repairs cannot add/delete files, edit unchanged files, traverse
symlinks/submodules, change executable modes, or escape allowed directories.

The second review uses the same configured model in a separate call without the
first call's conclusions. It is not a different-model verifier, proof of correctness,
or a measured review-quality improvement. Context covers changed files, not the
whole dependency graph. Failed CI currently escalates; automated log diagnosis,
conflict resolution and responding to human review threads remain future work.

Each externally visible write has a committed intent before dispatch and a receipt
after success. If a response is lost, Harness4 does **not** retry that write. To
query GitHub evidence and recover confirmed success without any model calls or
remote writes, add `--reconcile` to the same command:

```sh
h4 ship-github --policy /opt/harness4/policies/project.json --pr 42 \
  --state-dir "$HOME/.local/state/harness4/project" \
  --model YOUR_MODEL --base-url https://YOUR_PROVIDER/v1 \
  --write --approve --reconcile
```

Recovery requires an exact review body/commit/state/actor match, or a single repair
commit with the expected parent and exactly matching changed-file contents. Ambiguous
or absent evidence remains blocked for operator inspection. A stale uncertain
approval must be dismissed on GitHub; a subsequent reconciliation records that
approval as failed, allowing work on a new revision. The CLI does not provide a force-reset option;
do not delete the journal to bypass uncertainty. Policy changes also require operator
migration/reconciliation; active PR tasks keep their original policy digest.

GitHub provides no atomic transaction combining a PR head comparison, check reads
and review submission. Harness4 checks freshness before and after approval and
attempts to dismiss its own approval if the revision or checks change. Branch
protection is mandatory, and a failed dismissal requires human attention. This is
not an exactly-once distributed transaction. One local coordinator may own a state
directory; multiple machines with different journals are not coordinated.

Review artifacts, intended repairs and final reports live in the private SQLite /
artifact directory. Treat them as confidential source-derived data. JSON output
includes the policy digest, review revisions, check-run IDs, per-call usage and an
artifact reference. Keep this directory when resuming a run.

## Protocol references

- [Git references: non-force updates](https://docs.github.com/en/rest/git/refs#update-a-reference)
- [Commit-pinned reviews and dismissal](https://docs.github.com/en/rest/pulls/reviews)
- [Check runs and their producing Apps](https://docs.github.com/en/rest/checks/runs)
- [Classic branch protection](https://docs.github.com/en/rest/branches/branch-protection)

## Optional learned review guidance

Version 0.6 adds `--learning-dir /trusted/state/learning` to pin an approved checklist
and record revision-bound feedback episodes. Initialize a production learning scope
with matching repository and model settings first. Use a separate directory from
`--state-dir`; both hold local locks. Review reports and durable effect identities
include the checklist hash. This does not expand write grants or CI/approval authority.
See [learning, evaluation and rollback](LEARNING.md) before enabling it.

## Offline GitHub Actions example

For policy inspection without model credentials, copy
[ship-observe.yml](../examples/ship-observe.yml) into your repository. It checks out
a pinned Harness4 revision separately from the trusted target base, installs only
Harness4, fetches the PR head as Git data and uploads an advisory JSON report. It
does not install or execute the target project. Review the pinned tool revision
before updating it. This example performs no AI review, repairs or approval; use
the operator CLI above for those capabilities.

[Common failures and recovery](TROUBLESHOOTING.md).
