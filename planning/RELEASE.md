# Public alpha release plan

The user's 2026-11-24 product direction is a usable MIT-licensed open-source
alternative for Claude Ship's PR workflow. This supersedes the bootstrap's one-issue
limit for this release increment. Original H4 dependency issues remain tracked; a
narrow PR review slice does not mark unrelated runtime issues complete.

## Implemented first slice

- Installable `h4 ship` CLI: pinned local Git diff, offline policy check, optional
  text-only model review, structured report, usage and model identity.
- Trusted observe policy, protected paths, change-size limit, explicit CI evidence.
- MIT, contribution/security docs, Python CI and a safe offline Actions example.

## Publication completed — 2026-11-24

- Public repository: https://github.com/YangZhongqiHealth/harness4
- MIT license, source and documentation verified remotely.
- 83 tests passed locally; wheel installation and end-to-end CLI smoke passed.
- GitHub CI passed tests and builds on Python 3.11–3.13 for `6bbb60d`.
- Commit author uses the GitHub noreply address.
- This is an alpha repository publication; no PyPI package has been released.

## Next product milestones

1. H4-002 implemented in 0.4.0a0: scripted provider, capability profiles/probes,
   native tools, structured output and streaming conformance. Qualify live endpoints next.
2. H4-003 persistence and review provenance; independently verify findings and
   report precision/recall on public benchmark cases.
3. Isolated fix proposals with tests, bounded execution, cancellation and audit.
4. Read-only GitHub status ingestion and head-SHA freshness checks.
5. Explicitly authorized GitHub posting and policy approvals, subject to branch
   protection. Never use the current advisory exit code as a merge permission.

No automatic repair, model-independent quality advantage, production security,
or learning performance is claimed by this alpha.
