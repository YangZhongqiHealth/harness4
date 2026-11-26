"""Exercise persistence, evaluation, activation and rollback without credentials."""
import asyncio
import json
import tempfile
from pathlib import Path

from harness4.learning.demo import demo

with tempfile.TemporaryDirectory(prefix='harness4-learning-') as directory:
    result = asyncio.run(demo(Path(directory) / 'state'))
    assert result['quality_claim'] is False
    assert result['baseline'] == result['restored'] != result['promoted']
    assert result['fresh_review_finding_count'] == 1
    assert result['rollback_review_finding_count'] == 0
    print(json.dumps(result, indent=2))
