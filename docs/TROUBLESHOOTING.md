# Troubleshooting

Start with `h4 --version`, `python --version` and the command's `--help`.
Use the same activated environment for installation and execution. Remove secrets
and private code before sharing output in an issue.

## Installation and local review

| Symptom | Check or next step |
|---|---|
| `h4: command not found` | Activate the environment used for `python -m pip install .`. Run `python -m harness4 --help` to distinguish a PATH problem from a missing installation. |
| `No module named harness4` | Install the checkout in this environment. Running an example from the source tree alone does not install the package. |
| Python is too old | Use Python 3.11 or newer to create the virtual environment. The CI matrix currently covers 3.11–3.13. |
| Invalid Git reference | Confirm the target is a Git repository and both refs resolve to commits. `HEAD~1` requires at least two commits. For a PR, use its merge base. |
| Changed files are missing | Local review compares committed revisions. Commit the intended change; uncommitted changes are not included. |
| No AI findings in the report | Without `--model`, local `ship` produces a policy report only. Configure a model endpoint and key to request an AI review. |
| `needs_human` with exit 0 | Local `ship` exits 0 when it produces a report, even when human review is needed. Never use this exit code as a merge gate. |

The README uses a macOS/Linux shell. On Windows, activate with
`.venv\Scripts\Activate.ps1` in PowerShell. Windows is not part of the CI matrix;
WSL provides a Linux environment for the documented workflow.

## Provider setup

Supply an explicit model identifier and Chat Completions-compatible base URL. Remote
endpoints require HTTPS; loopback HTTP is allowed for local servers. Set the key in
`H4_MODEL_KEY`, or use `--key-env` to name another environment variable. Never pass
the key itself as an argument. Do not paste it into an issue.

```sh
h4 doctor --offline --model YOUR_MODEL --base-url https://YOUR_PROVIDER/v1
```

Offline diagnostics inspect declared configuration; they do **not** test connectivity
or authenticate. Add `--probe` instead of `--offline` for an explicitly authorized
live probe, which sends requests and may cost money. A successful probe does not
qualify the complete PR workflow. See [provider diagnostics](PROVIDERS.md).

## GitHub workflow

| Status or failure | Next step |
|---|---|
| Authentication or repository access fails | `gh auth login` does not populate `H4_GITHUB_TOKEN`. Check the named environment variable and repository-scoped user-token permissions. |
| Protected/unsupported paths | Inspect the operator policy and the supported PR types. The example protects tests, workflows, security and auth code; a PR touching them needs human handling. |
| `waiting_checks` | Confirm the exact head SHA, check-run names and App IDs. Resume with the same policy and state directory after CI finishes. |
| `needs_human` | Inspect findings, failed checks, mergeability and the repair budget. Rerunning does not fix unsupported CI failures or conflicts. |
| `blocked` after an uncertain write | Keep the journal. Use the documented `--reconcile` operation to read remote evidence. Never delete state to force a retry. |
| Approval is blocked | Check separate writer/approver/author identities and classic branch protection. Ruleset-only repositories are not supported. |
| State directory is locked | Stop or wait for the existing coordinator. Do not remove the lock or start another journal for the same in-flight work. |

The full [GitHub guide](GITHUB_WORKFLOW.md) defines permissions, polling bounds and
recovery. A successful approval is revision-specific, not a guarantee of correctness.

## Learning

Learning is optional. Recording episodes does not start an evaluation or spend a
learning budget. Initialize a production store with the same repository and model
profile as the GitHub run, using a directory separate from the write journal.

An `inconclusive` or rejected report cannot be promoted. Inspect missing evidence,
source-group overlap, confidence bounds and regression results. Do not weaken gates
just to obtain eligibility. Release cohorts are consumed even if an evaluation is
interrupted; use fresh cohorts for another release attempt.

Demo stores cannot supply production guidance. Retain the production store to inspect
reports, approvals and rollback targets. See [learning operations](LEARNING.md).
