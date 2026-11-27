# Project status

Updated 2026-11-26 · **0.6.0a0 public alpha** · MIT · No PyPI release.

| Capability | Status | Evidence |
|---|---|---|
| Local committed-diff review | Implemented; advisory and read-only | Git fixtures and CLI/model-response tests |
| Compatible model gateway | Implemented; live endpoint qualification pending | Offline tool, structured-output, SSE and error tests |
| SQLite state and artifacts | Implemented | Transaction, scoped-access, fencing and process-crash tests |
| GitHub review → repair → approval | Implemented; live PR qualification pending | 61 workflow cases with simulated HTTP and real SQLite |
| Checklist learning and release | Implemented; live gains unmeasured | 43 learning cases covering evidence, evaluation, activation, rollback and retraction |
| General task admission and tool execution | Interfaces/foundations only | Not a usable general agent runtime |

## Validation

The current suite contains **290 automated tests**. CI covers Python 3.11–3.13,
installed command/example smoke checks and package builds. CI also runs the local
review, GitHub and learning suites against the built wheel outside the source tree.
[Validation coverage and reproduction](../tests/VALIDATION.md).

Tests demonstrate lifecycle behavior with scripted model replies and simulated
GitHub responses. They do not establish live provider compatibility, review accuracy,
repair success rates or learning gains. No comparative quality or cost advantage over
Claude Ship has been measured.

## Supported operating boundary

GitHub support is limited to same-repository text PRs and classic branch protection.
Observation is the default. Writes require both CLI opt-in and operator-policy grants;
approval additionally requires a separate GitHub user credential. No PR code is
executed in the coordinator and no merge endpoint is called.

Learning changes review checklists only. Release evaluation uses fresh cohorts,
explicit budgets and verified labels. Activation requires separate operator approval.
The local OS owner and evaluator configuration are trusted; proposer isolation is
logical, not an OS sandbox.

## Next work

Live qualification, independent quality benchmarks, App/webhook onboarding and
isolated CI/conflict/feedback repair are priorities. See the [roadmap](ROADMAP.md)
for acceptance criteria and contribution opportunities.
