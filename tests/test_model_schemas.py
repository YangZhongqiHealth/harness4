"""Provider boundary compatibility and import direction checks."""
import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from harness4 import model_contracts as model
from harness4.contracts import Record

ROOT=Path(__file__).resolve().parents[1]
RECORDS={name:value for name,value in vars(model).items() if isinstance(value,type) and issubclass(value,Record) and value.__module__==model.__name__}


def test_provider_schema_snapshot():
    expected=json.loads((ROOT/'tests/fixtures/model-schemas-v1.json').read_text())
    assert expected=={name:cls.model_json_schema() for name,cls in RECORDS.items()}


@pytest.mark.parametrize('name', sorted(RECORDS))
def test_model_record_compatibility(name):
    record=RECORDS[name]
    fixtures=json.loads((ROOT/'tests/fixtures/model-records-v1.json').read_text())
    obj=record.model_validate_json(json.dumps(fixtures[name]))
    assert record.model_validate_json(obj.model_dump_json())==obj
    for bad in ({'schema_version':2},{'api_key':'secret-canary'},{'grant':'shell'}):
        with pytest.raises(ValidationError):
            record.model_validate_json(json.dumps(fixtures[name]|bad))


def test_model_core_cannot_import_adapters():
    allowed={'__future__','json','typing','pydantic','collections'}
    for module in ('model_contracts','model_ports'):
        tree=ast.parse((ROOT/f'src/harness4/{module}.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                assert all(alias.name.split('.')[0] in allowed for alias in node.names)
            elif isinstance(node,ast.ImportFrom):
                assert (node.level==1 and node.module in {'contracts','model_contracts'}) or (node.level==0 and node.module.split('.')[0] in allowed)
