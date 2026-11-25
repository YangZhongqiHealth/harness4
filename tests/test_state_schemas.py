import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness4 import state_contracts as state

ROOT=Path(__file__).resolve().parents[1]
RECORDS={'StoredStep':state.StoredStep,'OperationView':state.OperationView}


def test_state_schema_snapshot():
    assert json.loads((ROOT/'tests/fixtures/state-schemas-v1.json').read_text())=={name:record.model_json_schema() for name,record in RECORDS.items()}


@pytest.mark.parametrize('name',RECORDS)
def test_state_wire_compatibility(name):
    value=json.loads((ROOT/'tests/fixtures/state-records-v1.json').read_text())[name]
    record=RECORDS[name]
    result=record.model_validate_json(json.dumps(value))
    assert record.model_validate_json(result.model_dump_json())==result
    for mutation in ({'schema_version':2},{'grants':['shell']}):
        with pytest.raises(ValidationError):
            record.model_validate_json(json.dumps(value|mutation))
