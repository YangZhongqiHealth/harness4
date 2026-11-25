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

## Before publishing

- Run tests and build/install smoke test; inspect distribution and secret scan.
- Initialize local Git and publish to the user's confirmed GitHub identity.
- Verify remote files and CI. An alpha repository publication is not a PyPI release.

## Next product milestones

1. Finish H4-002 provider interfaces: scripted provider, capability profiles/probes,
   native tools and streaming conformance. Current adapter is text-only.
2. H4-003 persistence and review provenance; independently verify findings and
   report precision/recall on public benchmark cases.
3. Isolated fix proposals with tests, bounded execution, cancellation and audit.
4. Read-only GitHub status ingestion and head-SHA freshness checks.
5. Explicitly authorized GitHub posting and policy approvals, subject to branch
   protection. Never use the current advisory exit code as a merge permission.

No automatic repair, model-independent quality advantage, production security,
or learning performance is claimed by this alpha.
