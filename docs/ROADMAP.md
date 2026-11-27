# Roadmap

The goal is an operable, model-portable open-source PR workflow with measurable,
reversible improvements to review guidance. Current capabilities are listed in
[project status](STATUS.md). Items below are planned work, not release promises.

| Priority | Work | Completion evidence |
|---|---|---|
| 1 | Qualify live providers and real PR workflows | Publish exact configurations, reproducible runs, costs and failure/recovery cases on opt-in test repositories. |
| 2 | Measure review quality and learning | Independently label cases; compare frozen baseline and candidate on fresh data; report uncertainty, false positives and regressions. |
| 3 | Improve GitHub onboarding | App installation, scoped credentials and webhook handling with signature verification, replay protection and durable event deduplication. |
| 4 | Verify findings independently | Test findings against relevant context and independent evidence; measure precision and missed defects. |
| 5 | Expand repair coverage | Isolated execution for CI failures, conflicts and review feedback, with credentials separated from PR code and adversarial isolation tests. |
| 6 | Prepare reproducible releases | Fresh-machine setup, package publication, upgrade/recovery instructions and a supported provider matrix. |

## Dependencies and boundaries

Live qualification and quality measurement can proceed with the current CLI.
Webhook automation needs authenticated ingress and durable event handling before
unattended writes. CI-log diagnosis and executable repairs require an isolated runner
and trusted tool authorization first. Fork support needs a separate credential and
repository trust model.

General admission and tool-broker services remain unfinished. Existing task-service
Protocols are foundations, not an implemented assistant, daemon or distributed runtime.
Multi-surface learning and generated executable policies need additional evaluators,
isolation and release controls before adoption.

## How improvement will be measured

Publish dataset provenance and permitted inputs, exact model/configuration versions,
budgets, outcomes and failure cases. Measure useful findings, false positives,
independently verified repairs, regressions, elapsed time, cost and recovery failures.
Disclose differences in model access or budget when comparing systems.

For learning, compare the frozen incumbent and candidate on unseen target cases plus
regression cases, with explicit uncertainty. Scripted demos and unit-test counts
establish mechanics, not better review quality.

Discuss substantial work in a [GitHub issue](https://github.com/YangZhongqiHealth/harness4/issues)
with a concrete acceptance test. See [Contributing](../CONTRIBUTING.md).
