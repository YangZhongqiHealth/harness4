# Security

The local `ship` command is advisory. The opt-in `ship-github` command can post
reviews, create restricted repair commits and approve using a separate GitHub user.
It is not a code sandbox. Prompts are not a security boundary; malicious source can
influence model conclusions. Review the deployment and limits in
[the GitHub workflow guide](docs/GITHUB_WORKFLOW.md) before granting write access.

The coordinator does not execute PR code. CI must run on separately isolated runners
without the coordinator credentials. Approval requires trusted, App-pinned checks and
classic branch protection. Keep policy and persistent state outside untrusted code.
GitHub writes are commit-pinned and journaled, but network ambiguity requires evidence
reconciliation, and head/check/review operations are not an atomic transaction.

Only send code to providers you are authorized to use. Credentials are read from an
environment variable inside the adapter; they are not report fields. Provider error
bodies are not surfaced. Successful model output is untrusted and may quote source
content; treat reports as having the same confidentiality as the reviewed code.

Use a trusted installed package and trusted policy when reviewing an untrusted PR.
The bundled Actions example installs the base branch and uses no secrets. Never
execute PR-controlled code in a job with write permissions or model credentials.

For vulnerabilities, use GitHub's private vulnerability reporting if enabled on the
published repository. If unavailable, open a minimal issue asking for a private
contact without exploit details, private code or secrets. Only the current alpha is
maintained; there is no production support commitment.
