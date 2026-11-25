"""Compatibility fixtures for the P0 contract boundary."""
import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from harness4 import contracts as c

ROOT = Path(__file__).resolve().parents[1]
RECORDS = {
    name: value for name, value in vars(c).items()
    if isinstance(value, type) and issubclass(value, c.Record) and value is not c.Record
}


def test_schema_fixture():
    fixture = json.loads((ROOT / 'tests/fixtures/contracts-v1.json').read_text())
    assert fixture == {name: record.model_json_schema() for name, record in RECORDS.items()}


@pytest.mark.parametrize('name', sorted(RECORDS))
def test_all_boundary_versions_and_unknown_fields(name):
    record = RECORDS[name]
    # Use the checked-in valid wire example, so failures are attributable to the mutation.
    wire = json.loads((ROOT / 'tests/fixtures/records-v1.json').read_text())[name]
    instance = record.model_validate_json(json.dumps(wire))
    assert record.model_validate_json(instance.model_dump_json()) == instance
    for mutation in ({'schema_version': 2}, {'grants': ['shell']}):
        with pytest.raises(ValidationError):
            record.model_validate_json(json.dumps(wire | mutation))


def test_unknown_status_and_usage():
    with pytest.raises(ValidationError):
        c.TaskSnapshot.model_validate_json('{"workspace_id":"w","task_id":"t","policy_hash":"p","status":"done"}')
    assert c.UsageSummary().input_tokens is None
    with pytest.raises(ValidationError):
        c.UsageSummary(input_tokens=-1)


def test_timestamp_and_policy_integrity():
    wire = json.loads((ROOT / 'tests/fixtures/records-v1.json').read_text())
    with pytest.raises(ValidationError):
        c.Event(**(wire['Event'] | {'timestamp': '2026-02-30T00:00:00.000000Z'}))
    with pytest.raises(ValidationError):
        c.PolicyView.model_validate_json(json.dumps(wire['PolicyView'] | {'policy_hash': 'stale'}))


def test_import_boundaries():
    for module in ('contracts', 'ports'):
        tree = ast.parse((ROOT / f'src/harness4/{module}.py').read_text())
        allowed = {'__future__', 'enum', 'hashlib', 'json', 'typing', 'pydantic', 'datetime', 'collections'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name.split('.')[0] in allowed for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert (module == 'ports' and node.level == 1 and node.module == 'contracts') or (
                    node.level == 0 and node.module.split('.')[0] in allowed)
