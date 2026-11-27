# Contributing

Start with [README](README.md) and [project status](docs/STATUS.md). Small contributions with a reproducible
problem and tests are welcome. Discuss large architectural changes in an issue first.

Use Python 3.11+, install `python -m pip install -e '.[dev]'`, and run
`python -m pytest -q` and `python scripts/check_docs.py`. CI checks Python 3.11–3.13 and builds the package. Add fixtures
for provider behavior; ordinary tests must not need credentials or paid API calls.

Keep core contracts independent of adapters. Record intentional contract changes in
an ADR and update compatibility fixtures. Include the problem, behavior change,
validation and remaining limitations in a pull request. Never include credentials,
private source diffs, raw provider logs or hidden model reasoning in test fixtures.

Review output is advisory. Changes that enable writes, execution or approvals need
explicit trusted authorization boundaries and negative tests before being enabled.
Contributions are distributed under the repository's MIT license.

Keep session handoffs, personal planning and agent scratch notes in the ignored
`.local-notes/` directory. Public documentation should describe supported behavior,
reproducible evidence or durable technical rationale. Propose future work through
[issues](https://github.com/YangZhongqiHealth/harness4/issues) and the
[roadmap](docs/ROADMAP.md).
