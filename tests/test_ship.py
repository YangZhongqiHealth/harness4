import asyncio
import json
import subprocess

import httpx
import pytest
from pydantic import ValidationError

from harness4.cli import collect_diff, main
from harness4.provider import ProviderFailure, complete
from harness4.ship import Review, ShipPolicy, evaluate_policy, parse_review


@pytest.fixture
def repo(tmp_path):
    def run(*args):
        return subprocess.run(['git', '-C', str(tmp_path), *args], capture_output=True, check=True).stdout
    run('init')
    run('config', 'user.name', 'Test')
    run('config', 'user.email', 'test@example.invalid')
    (tmp_path / 'app.py').write_text('value = 1\n')
    run('add', '.')
    run('commit', '-m', 'base')
    (tmp_path / 'app.py').write_text('value = 2\n')
    run('add', '.')
    run('commit', '-m', 'head')
    return tmp_path


def test_cli_offline_report_and_commit_pins(repo, capsys):
    assert main(['ship', '--repo', str(repo), '--base', 'HEAD~1']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['changed_files'] == ['app.py']
    assert report['changed_lines'] == 2
    assert report['base_sha'] != report['head_sha']
    assert report['recommendation'] == 'needs_human'
    assert report['checks'] == 'unknown'
    assert report['usage']['input_tokens'] is None


def test_fixture_never_eligible(repo, capsys, tmp_path):
    fixture = tmp_path / 'review.json'
    fixture.write_text('{"summary":"fixture","findings":[]}')
    assert main(['ship', '--repo', str(repo), '--base', 'HEAD~1', '--review-file', str(fixture), '--checks', 'passed']) == 0
    assert json.loads(capsys.readouterr().out)['recommendation'] == 'needs_human'


@pytest.mark.parametrize('changes', [
    {'checks': 'failed'}, {'checks': 'unknown'}, {'changed_lines': 501},
    {'files': ('.github/workflows/test.yml',)}, {'files': ()}, {'source': 'fixture'},
])
def test_policy_blocks(changes):
    args = dict(files=('app.py',), changed_lines=2, checks='passed', review=Review(summary='Reviewed'), source='model')
    args.update(changes)
    assert evaluate_policy(ShipPolicy(), **args)[0] == 'needs_human'


def test_advisory_eligibility_and_blocking_finding():
    args = dict(files=('app.py',), changed_lines=2, checks='passed', source='model')
    assert evaluate_policy(ShipPolicy(), review=Review(summary='Reviewed'), **args) == ('eligible', ())
    review = parse_review(json.dumps({'summary':'Bug', 'findings':[dict(severity='high',path='app.py',line=1,title='Bug',explanation='Evidence')]}), ('app.py',))
    assert evaluate_policy(ShipPolicy(), review=review, **args)[0] == 'needs_human'
    with pytest.raises(ValueError):
        parse_review(review.model_dump_json(), ('other.py',))
    with pytest.raises(ValidationError):
        ShipPolicy(mode='approve')


def test_git_does_not_execute_external_diff(repo, tmp_path):
    sentinel = tmp_path / 'executed'
    subprocess.run(['git', '-C', str(repo), 'config', 'diff.external', f'touch {sentinel}'], check=True)
    assert collect_diff(str(repo), 'HEAD~1', 'HEAD')[4] == 2
    assert not sentinel.exists()


def test_invalid_ref_safe_error(repo, capsys):
    assert main(['ship', '--repo', str(repo), '--base', 'does-not-exist']) == 2
    assert 'Traceback' not in capsys.readouterr().err


def response(**overrides):
    data = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{"summary":"Reviewed","findings":[]}'}}]}
    data.update(overrides)
    return data


def call(handler, **overrides):
    args = dict(base_url='https://example.invalid/v1', model='test', key_env='H4_TEST_KEY',
                system='review', prompt='diff', request_id='req', transport=httpx.MockTransport(handler))
    args.update(overrides)
    return asyncio.run(complete(**args))


def test_provider_request_unknown_usage(monkeypatch):
    monkeypatch.setenv('H4_TEST_KEY', 'test-secret-canary')
    def handler(request):
        assert str(request.url) == 'https://example.invalid/v1/chat/completions'
        assert request.headers['Authorization'] == 'Bearer test-secret-canary'
        body = json.loads(request.content)
        assert body['stream'] is False and 'tools' not in body
        assert body['max_tokens'] == 4096
        return httpx.Response(200, json=response())
    text, usage = call(handler)
    assert json.loads(text)['summary'] == 'Reviewed'
    assert usage.input_tokens is None


@pytest.mark.parametrize('status,code', [(401,'NOT_AUTHORIZED'),(403,'NOT_AUTHORIZED'),(429,'TRANSIENT_PROVIDER'),(500,'TRANSIENT_PROVIDER'),(302,'INVALID_INPUT')])
def test_provider_errors_redacted_no_retry(status, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text='private-key-canary', headers={'location':'https://other.invalid'})
    with pytest.raises(ProviderFailure) as caught:
        call(handler)
    assert caught.value.error.code == code
    assert 'canary' not in caught.value.error.model_dump_json()
    assert len(calls) == 1


@pytest.mark.parametrize('finish', ['length','content_filter','tool_calls',None])
def test_incomplete_output_rejected(finish):
    data = response()
    data['choices'][0]['finish_reason'] = finish
    with pytest.raises(ProviderFailure, match='invalid or incomplete'):
        call(lambda _: httpx.Response(200, json=data))


def test_timeout_and_bad_usage():
    def timeout(request):
        raise httpx.ReadTimeout('secret-canary')
    with pytest.raises(ProviderFailure) as caught:
        call(timeout)
    assert caught.value.error.code == 'TIMEOUT'
    with pytest.raises(ProviderFailure):
        call(lambda _: httpx.Response(200, json=response(usage={'prompt_tokens': -1})))


@pytest.mark.parametrize('url', ['http://example.com/v1','https://user:secret@example.com/v1','https://example.com/v1?key=secret'])
def test_endpoint_rejected_without_request(url):
    def handler(request):
        pytest.fail('must not dispatch')
    with pytest.raises(ProviderFailure):
        call(handler, base_url=url)


def test_cli_live_with_mock_transport(repo, monkeypatch, capsys):
    async def fake_complete(**kwargs):
        assert 'value = 2' in kwargs['prompt']
        from harness4.contracts import UsageSummary
        return '{"summary":"Reviewed","findings":[]}', UsageSummary(input_tokens=42, output_tokens=10)
    monkeypatch.setattr('harness4.cli.complete', fake_complete)
    assert main(['ship','--repo',str(repo),'--base','HEAD~1','--model','test','--base-url','https://example.invalid/v1','--checks','passed']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['recommendation'] == 'eligible'
    assert report['usage']['input_tokens'] == 42
    assert report['mode'] == 'observe'


@pytest.mark.parametrize('kind', ['binary', 'oversized'])
def test_unreviewable_diff_fails_before_provider(repo, monkeypatch, kind, capsys):
    target = repo / 'app.py'
    target.write_bytes(b'\x00binary' if kind == 'binary' else b'x' * 200_001)
    subprocess.run(['git','-C',str(repo),'add','.'], check=True)
    subprocess.run(['git','-C',str(repo),'commit','-m','unreviewable'], capture_output=True, check=True)
    async def forbidden(**kwargs):
        pytest.fail('unreviewable diff must not be sent')
    monkeypatch.setattr('harness4.cli.complete', forbidden)
    assert main(['ship','--repo',str(repo),'--base','HEAD~1','--model','test','--base-url','https://example.invalid']) == 2
    assert 'approval' in capsys.readouterr().err


def test_rename_out_of_protected_path_still_protected(repo):
    folder = repo / 'auth'
    folder.mkdir()
    (folder / 'config.py').write_text('x = 1\n')
    subprocess.run(['git','-C',str(repo),'add','.'], check=True)
    subprocess.run(['git','-C',str(repo),'commit','-m','protected'], capture_output=True, check=True)
    (folder / 'config.py').rename(repo / 'config.py')
    subprocess.run(['git','-C',str(repo),'add','.'], check=True)
    subprocess.run(['git','-C',str(repo),'commit','-m','rename'], capture_output=True, check=True)
    _, _, files, _, lines = collect_diff(str(repo), 'HEAD~1', 'HEAD')
    assert 'auth/config.py' in files
    decision, reasons = evaluate_policy(ShipPolicy(), files=files, changed_lines=lines, checks='passed', review=Review(summary='Reviewed'), source='model')
    assert decision == 'needs_human'
    assert any('Protected' in reason for reason in reasons)


@pytest.mark.parametrize('payload', [
    b'not-json', b'[]', b'{"choices":[]}',
    json.dumps(response(usage={'prompt_tokens': True})).encode(),
    json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'ok','tool_calls':[{}]}}]}).encode(),
    json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'ok','refusal':'no'}}]}).encode(),
    b'x' * 1_000_001,
])
def test_malformed_responses_fail_closed(payload):
    with pytest.raises(ProviderFailure):
        call(lambda _: httpx.Response(200, content=payload))


def test_known_usage_and_loopback():
    _, usage = call(lambda _: httpx.Response(200, json=response(usage={'prompt_tokens':7,'completion_tokens':3})), base_url='http://127.0.0.1:1234/v1')
    assert usage.input_tokens == 7 and usage.output_tokens == 3


def test_model_output_cannot_widen_review_schema():
    with pytest.raises(ValidationError):
        parse_review('{"summary":"ok","approve":true}', ('app.py',))
    with pytest.raises(ValidationError):
        ShipPolicy.model_validate_json('{"mode":"observe","shell":true}')


def test_provider_wall_clock_deadline():
    async def slow(request):
        await asyncio.sleep(0.1)
        return httpx.Response(200, json=response())
    with pytest.raises(ProviderFailure) as caught:
        call(slow, timeout=0.01)
    assert caught.value.error.code == 'TIMEOUT'
