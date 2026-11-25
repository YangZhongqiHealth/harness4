import asyncio
import base64
import copy
import json

import httpx
import pytest

from harness4.adapters.sqlite_state import SQLiteState
from harness4.github import GitHub, GitHubFailure
from harness4.github_workflow import (GitHubPolicy, WorkflowJournal, run_workflow, Repair,
                                      replacements, safe_path)

A, B, C, T, U, F = (c * 40 for c in 'abcdef')
CLEAN = json.dumps({'summary': 'No defect found.', 'findings': []})
BUG = json.dumps({'summary': 'Found a defect.', 'findings': [
    {'severity': 'high', 'path': 'src/app.py', 'line': 1, 'title': 'Wrong answer',
     'explanation': 'The expected value is two.'}]})
FIX = json.dumps({'summary': 'Use two.', 'replacements': [
    {'path': 'src/app.py', 'old_text': 'value = 1', 'new_text': 'value = 2'}]})


def policy(**changes):
    return GitHubPolicy.model_validate_json(json.dumps({
        'repository': 'owner/project', 'base_branch': 'main',
        'required_checks': [{'name': 'tests', 'app_id': 123}],
        'repair_prefixes': ['src/'], 'allow_repair': True, 'allow_approval': True, **changes}))


class Server:
    def __init__(self):
        self.head, self.base, self.source = A, B, 'value = 1\n'
        self.writes, self.reviews, self.calls = [], [], []
        self.check_state, self.check_app, self.check_head = 'success', 123, None
        self.mergeable, self.draft, self.fork = True, False, False
        self.mode, self.filename, self.status = '100644', 'src/app.py', 'modified'
        self.protected, self.author, self.approver = True, 7, 2
        self.drop = None
        self.on_request = None
        self.missing_files = False
        self.patch = '@@ -1 +1 @@\n-value = 0\n+value = 1'
        self.counter = 0

    def handler(self, request):
        path = request.url.path.removeprefix('/repos/owner/project/')
        method = request.method
        body = json.loads(request.content) if request.content else None
        self.calls.append((method, path, body))
        if self.on_request:
            self.on_request(method, path, body)
        if method != 'GET':
            self.writes.append((method, path, body))
        if path == '/user':
            return httpx.Response(200, json={'id': self.approver if request.headers['authorization'] == 'Bearer approve' else 1})
        if path == 'pulls/1':
            result = {'state': 'open', 'draft': self.draft, 'merged': False, 'changed_files': 1,
                      'user': {'id': self.author}, 'mergeable': self.mergeable, 'mergeable_state': 'blocked',
                      'head': {'sha': self.head, 'ref': 'fix', 'repo': {'full_name': 'fork/project' if self.fork else 'owner/project'}},
                      'base': {'sha': self.base, 'ref': 'main', 'repo': {'full_name': 'owner/project'}}}
        elif path == 'branches/main/protection':
            result = {'required_pull_request_reviews': {'dismiss_stale_reviews': self.protected,
                                                        'require_last_push_approval': self.protected},
                      'required_status_checks': {'strict': True, 'checks': [{'context': 'tests', 'app_id': 123}]}}
        elif path == 'pulls/1/files':
            result = [] if self.missing_files else [{'filename': self.filename, 'sha': F, 'status': self.status,
                                                     'additions': 1, 'deletions': 1, 'patch': self.patch}]
        elif path == f'git/blobs/{F}':
            result = {'encoding': 'base64', 'content': base64.b64encode(self.source.encode()).decode(),
                      'size': len(self.source.encode())}
        elif path.startswith('commits/') and path.endswith('/check-runs'):
            result = {'total_count': 1, 'check_runs': [{'id': 99, 'name': 'tests', 'app': {'id': self.check_app},
                       'head_sha': self.check_head or self.head,
                       'status': 'in_progress' if self.check_state == 'pending' else 'completed',
                       'conclusion': self.check_state}]}
        elif path == 'pulls/1/reviews':
            if method == 'GET':
                result = self.reviews
            else:
                result = {'id': len(self.reviews) + 1, 'commit_id': body['commit_id'], 'body': body['body'],
                          'user': {'id': self.approver if request.headers['authorization'] == 'Bearer approve' else 1},
                          'state': 'APPROVED' if body['event'] == 'APPROVE' else 'COMMENTED'}
                self.reviews.append(result)
                if self.drop == body['event']:
                    raise httpx.ReadError('contains-secret', request=request)
        elif path.endswith('/dismissals'):
            review_id = int(path.split('/')[-2])
            self.reviews[review_id - 1]['state'] = 'DISMISSED'
            result = self.reviews[review_id - 1]
        elif path.startswith('pulls/1/reviews/'):
            result = self.reviews[int(path.split('/')[-1]) - 1]
        elif path == f'git/commits/{A}':
            result = {'tree': {'sha': T}}
        elif path == f'git/trees/{T}':
            result = {'tree': [{'path': 'src', 'type': 'tree', 'mode': '040000', 'sha': U}]}
        elif path == f'git/trees/{U}':
            result = {'tree': [{'path': 'app.py', 'type': 'blob', 'mode': self.mode, 'sha': F}]}
        elif path == f'compare/{A}...{C}':
            result = {'total_commits': 1, 'commits': [{'parents': [{'sha': A}]}],
                      'files': [{'filename': 'src/app.py', 'sha': F, 'status': 'modified'}]}
        elif path == 'git/trees':
            self.pending_source = body['tree'][0]['content']
            result = {'sha': U}
        elif path == 'git/commits':
            assert body['parents'] == [A]
            result = {'sha': C}
        elif path == 'git/refs/heads/fix':
            assert body == {'sha': C, 'force': False}
            if self.head != A:
                return httpx.Response(422, json={})
            self.head, self.source = C, self.pending_source
            result = {'object': {'sha': C}}
            if self.drop == 'repair':
                raise httpx.ReadError('secret', request=request)
        else:
            raise AssertionError((method, path, body))
        return httpx.Response(200, json=copy.deepcopy(result))


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setenv('WRITER', 'write')
    monkeypatch.setenv('APPROVER', 'approve')
    return Server()


def run(tmp_path, server, script, *, config=None, write=True, approve=True, polls=1, reconcile=False):
    calls = []
    async def model(system, payload):
        calls.append((system, payload))
        answer = script.pop(0)
        if callable(answer):
            return answer()
        return answer
    async def execute():
        transport = httpx.MockTransport(server.handler)
        p = config or policy()
        with SQLiteState(tmp_path / 'state') as state:
            journal = WorkflowJournal(state, p, 1)
            try:
                return await run_workflow(GitHub(p.repository, key_env='WRITER', transport=transport), p, 1,
                    model, journal, write=write, approve=approve,
                    approver=GitHub(p.repository, key_env='APPROVER', transport=transport),
                    check_polls=polls, poll_seconds=0, reconcile=reconcile)
            finally:
                await journal.close()
    result = asyncio.run(execute())
    return result, calls


def test_review_repair_rereview_ci_approval_and_restart_dedup(tmp_path, server):
    result, calls = run(tmp_path, server, [BUG, CLEAN, FIX, CLEAN, CLEAN])
    assert result['status'] == 'approved'
    assert [r['head_sha'] for r in result['reports']] == [A, C]
    assert len(calls) == 5
    assert server.source == 'value = 2\n'
    approvals = [b for _, _, b in server.writes if b.get('event') == 'APPROVE']
    assert len(approvals) == 1 and approvals[0]['commit_id'] == C
    writes = len(server.writes)
    assert run(tmp_path, server, [CLEAN, CLEAN])[0]['status'] == 'approved'
    assert len(server.writes) == writes


def test_observe_never_writes(tmp_path, server):
    result, _ = run(tmp_path, server, [CLEAN, CLEAN], write=False, approve=False)
    assert result['status'] == 'eligible' and result['approved'] is False
    assert not server.writes


@pytest.mark.parametrize('state,expected', [('failure', 'needs_human'), ('pending', 'waiting_checks'),
                                           ('skipped', 'needs_human'), ('neutral', 'needs_human')])
def test_ci_gates(tmp_path, server, state, expected):
    server.check_state = state
    result, _ = run(tmp_path, server, [CLEAN, CLEAN])
    assert result['status'] == expected
    assert not any(b.get('event') == 'APPROVE' for _, _, b in server.writes)


@pytest.mark.parametrize('attr,value', [('check_app', 999), ('check_head', B)])
def test_ci_wrong_app_or_head_not_evidence(tmp_path, server, attr, value):
    setattr(server, attr, value)
    assert run(tmp_path, server, [CLEAN, CLEAN])[0]['status'] == 'waiting_checks'


def test_wait_resume_after_ci(tmp_path, server):
    server.check_state = 'pending'
    assert run(tmp_path, server, [BUG, CLEAN, FIX, CLEAN, CLEAN])[0]['status'] == 'waiting_checks'
    server.check_state = 'success'
    assert run(tmp_path, server, [CLEAN, CLEAN])[0]['status'] == 'approved'
    assert len([p for m, p, _ in server.writes if m == 'PATCH']) == 1


@pytest.mark.parametrize('attr,value', [('draft', True), ('fork', True), ('protected', False),
                                       ('approver', 1), ('author', 2), ('missing_files', True),
                                       ('filename', '.github/workflows/ci.yml'), ('status', 'renamed'),
                                       ('patch', None), ('filename', '../bad')])
def test_reject_unsupported_or_unsafe_pr_before_writes(tmp_path, server, attr, value):
    setattr(server, attr, value)
    with pytest.raises(GitHubFailure):
        run(tmp_path, server, [CLEAN, CLEAN])
    assert not server.writes


def test_findings_from_second_pass_block(tmp_path, server):
    result, _ = run(tmp_path, server, [CLEAN, BUG], config=policy(allow_repair=False))
    assert result['status'] == 'needs_human'
    assert not any(b.get('event') == 'APPROVE' for _, _, b in server.writes)


def test_stale_head_during_review(tmp_path, server):
    def move():
        server.head = C
        return CLEAN
    with pytest.raises(GitHubFailure, match='changed'):
        run(tmp_path, server, [CLEAN, move])
    assert not server.writes


def test_stale_base_during_review(tmp_path, server):
    def move():
        server.base = C
        return CLEAN
    with pytest.raises(GitHubFailure, match='changed'):
        run(tmp_path, server, [CLEAN, move])
    assert not server.writes


def test_concurrent_push_after_approval_is_dismissed(tmp_path, server):
    def change(method, path, body):
        if body and body.get('event') == 'APPROVE':
            server.head = C
    server.on_request = change
    with pytest.raises(GitHubFailure, match='dismissed'):
        run(tmp_path, server, [CLEAN, CLEAN])
    assert server.reviews[-1]['state'] == 'DISMISSED'


@pytest.mark.parametrize('drop,script', [('COMMENT', [CLEAN, CLEAN]), ('APPROVE', [CLEAN, CLEAN]),
                                       ('repair', [BUG, CLEAN, FIX])])
def test_unknown_write_blocks_restart_without_repeating_effect(tmp_path, server, drop, script):
    server.drop = drop
    with pytest.raises(GitHubFailure):
        run(tmp_path, server, script)
    count = len(server.writes)
    server.drop = None
    with pytest.raises(GitHubFailure, match='unknown effect'):
        run(tmp_path, server, [])
    assert len(server.writes) == count


def test_durable_repair_budget(tmp_path, server):
    server.check_state = 'pending'
    p = policy(max_repair_rounds=1)
    assert run(tmp_path, server, [BUG, CLEAN, FIX, CLEAN, CLEAN], config=p)[0]['status'] == 'waiting_checks'
    assert run(tmp_path, server, [BUG, CLEAN], config=p)[0]['status'] == 'needs_human'
    assert len([x for x in server.writes if x[0] == 'PATCH']) == 1


def test_policy_change_requires_explicit_reconciliation(tmp_path, server):
    run(tmp_path, server, [CLEAN, CLEAN], approve=False)
    with pytest.raises(GitHubFailure, match='different policy'):
        run(tmp_path, server, [], config=policy(max_repair_rounds=1), approve=False)


@pytest.mark.parametrize('mode', ['120000', '160000'])
def test_repair_rejects_link_or_submodule(tmp_path, server, mode):
    server.mode = mode
    with pytest.raises(GitHubFailure, match='regular file'):
        run(tmp_path, server, [BUG, CLEAN, FIX])
    assert not any(m == 'PATCH' for m, _, _ in server.writes)


@pytest.mark.parametrize('replacement', [
    {'path': 'other.py', 'old_text': 'value = 1', 'new_text': 'x'},
    {'path': 'src/app.py', 'old_text': 'absent', 'new_text': 'x'},
    {'path': 'src/app.py', 'old_text': 'value = 1', 'new_text': 'value = 1'},
])
def test_repair_bounds(replacement):
    repair = Repair.model_validate_json(json.dumps({'summary': 'fix', 'replacements': [replacement]}))
    with pytest.raises(GitHubFailure):
        replacements(repair, {'src/app.py': 'value = 1\n'}, policy())


def test_findings_line_validation(tmp_path, server):
    review = json.loads(BUG)
    review['findings'][0]['line'] = 999
    with pytest.raises(GitHubFailure, match='outside'):
        run(tmp_path, server, [json.dumps(review)])
    assert not server.writes


def test_missing_credentials_and_redirect_no_leak(monkeypatch):
    monkeypatch.delenv('NO_KEY', raising=False)
    with pytest.raises(GitHubFailure, match='empty'):
        asyncio.run(GitHub('owner/project', key_env='NO_KEY').api('GET', 'pulls/1'))
    monkeypatch.setenv('NO_KEY', 'secret-value')
    transport = httpx.MockTransport(lambda r: httpx.Response(302, headers={'location': 'https://evil.invalid'}))
    with pytest.raises(GitHubFailure, match='302') as exc:
        asyncio.run(GitHub('owner/project', key_env='NO_KEY', transport=transport).api('GET', 'pulls/1'))
    assert 'secret-value' not in str(exc.value)


def test_pagination_collects_all_and_bounds(monkeypatch):
    monkeypatch.setenv('NO_KEY', 'secret')
    def handler(request):
        page = int(request.url.params['page'])
        return httpx.Response(200, json=list(range(100)) if page == 1 else [100])
    api = GitHub('owner/project', key_env='NO_KEY', transport=httpx.MockTransport(handler))
    assert len(asyncio.run(api.pages('pulls/1/files'))) == 101
    api.transport = httpx.MockTransport(lambda r: httpx.Response(200, json=list(range(100))))
    with pytest.raises(GitHubFailure, match='pagination limit'):
        asyncio.run(api.pages('pulls/1/files'))


@pytest.mark.parametrize('path', ['../src', '/src', 'src//a', 'src/./a', 'src\\a', 'src/\na'])
def test_path_validation(path):
    assert not safe_path(path)


@pytest.mark.parametrize('drop,script', [('COMMENT', [CLEAN, CLEAN]), ('APPROVE', [CLEAN, CLEAN]),
                                       ('repair', [BUG, CLEAN, FIX])])
def test_explicit_reconciliation_is_read_only_and_proves_remote_success(tmp_path, server, drop, script):
    server.drop = drop
    with pytest.raises(GitHubFailure):
        run(tmp_path, server, script)
    count = len(server.writes)
    server.drop = None
    result, calls = run(tmp_path, server, [], reconcile=True)
    assert result['status'] == 'reconciled' and not calls
    assert len(server.writes) == count
    assert run(tmp_path, server, [CLEAN, CLEAN])[0]['status'] == 'approved'


def test_uncertain_approval_on_new_head_cannot_be_reconciled(tmp_path, server):
    server.drop = 'APPROVE'
    with pytest.raises(GitHubFailure):
        run(tmp_path, server, [CLEAN, CLEAN])
    server.head = C
    with pytest.raises(GitHubFailure, match='stale'):
        run(tmp_path, server, [], reconcile=True)


def test_changed_base_does_not_reuse_old_approval(tmp_path, server):
    run(tmp_path, server, [CLEAN, CLEAN])
    server.base = C
    run(tmp_path, server, [CLEAN, CLEAN])
    assert len([b for _, _, b in server.writes if b.get('event') == 'APPROVE']) == 2


def test_dismissed_approval_is_not_reported_as_approved(tmp_path, server):
    run(tmp_path, server, [CLEAN, CLEAN])
    server.reviews[-1]['state'] = 'DISMISSED'
    with pytest.raises(GitHubFailure, match='no longer active'):
        run(tmp_path, server, [CLEAN, CLEAN])


def test_ci_changes_during_approval_dismisses_it(tmp_path, server):
    def change(method, path, body):
        if body and body.get('event') == 'APPROVE':
            server.check_state = 'failure'
    server.on_request = change
    with pytest.raises(GitHubFailure, match='dismissed'):
        run(tmp_path, server, [CLEAN, CLEAN])
    assert server.reviews[-1]['state'] == 'DISMISSED'


def test_ci_freshness_changes_before_approval(tmp_path, server):
    def change(method, path, body):
        if path.endswith('/check-runs'):
            server.counter += 1
            if server.counter == 2:
                server.check_state = 'failure'
    server.on_request = change
    with pytest.raises(GitHubFailure, match='CI evidence changed'):
        run(tmp_path, server, [CLEAN, CLEAN])
    assert not any(b.get('event') == 'APPROVE' for _, _, b in server.writes)


def test_repair_concurrent_push_is_not_overwritten(tmp_path, server):
    def change(method, path, body):
        if method == 'PATCH':
            server.head = B
    server.on_request = change
    with pytest.raises(GitHubFailure, match='422'):
        run(tmp_path, server, [BUG, CLEAN, FIX])
    assert server.head == B


def test_approval_requires_explicit_two_part_grant(tmp_path, server):
    with pytest.raises(GitHubFailure, match='opt-in'):
        run(tmp_path, server, [], write=False)
    with pytest.raises(GitHubFailure, match='opt-in'):
        run(tmp_path, server, [], config=policy(allow_approval=False))
    assert not server.writes


def test_repair_line_budget():
    repair = Repair.model_validate_json(json.dumps({'summary': 'fix', 'replacements': [
        {'path': 'src/app.py', 'old_text': 'one', 'new_text': 'two\nthree\nfour'}]}))
    with pytest.raises(GitHubFailure, match='line budget'):
        replacements(repair, {'src/app.py': 'one'}, policy(max_changed_lines=2))


def test_transport_response_limit(monkeypatch):
    monkeypatch.setenv('TOKEN', 'secret')
    api = GitHub('owner/project', key_env='TOKEN', transport=httpx.MockTransport(
        lambda r: httpx.Response(200, content=b'x' * 2_000_001)))
    with pytest.raises(GitHubFailure, match='size limit'):
        asyncio.run(api.api('GET', 'pulls/1'))


def test_cli_end_to_end_and_safe_blocked_report(tmp_path, server, monkeypatch, capsys):
    from harness4.cli import main
    import harness4.github_cli as cli
    transport = httpx.MockTransport(server.handler)
    monkeypatch.setattr(cli, 'GitHub', lambda repo, key_env: GitHub(repo, key_env=key_env, transport=transport))
    async def complete(**kwargs):
        from harness4.contracts import UsageSummary
        return CLEAN, UsageSummary()
    monkeypatch.setattr(cli, 'complete', complete)
    path = tmp_path / 'policy.json'
    path.write_text(policy().model_dump_json())
    args = ['ship-github', '--policy', str(path), '--pr', '1', '--state-dir', str(tmp_path / 'state'),
            '--model', 'test', '--base-url', 'https://example.invalid/v1', '--github-key-env', 'WRITER',
            '--approval-key-env', 'APPROVER', '--write', '--approve']
    assert main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'approved' and len(report['model_calls']) == 2
    assert report['model_calls'][0]['usage']['input_tokens'] is None
    assert report['artifact']['digest'].startswith('sha256:')
    server.draft = True
    assert main(args) == 3
    assert json.loads(capsys.readouterr().out)['status'] == 'blocked'


@pytest.mark.parametrize('path', ['//evil.invalid', '/repos/a/../secret', '/repos/a/%2e%2e/secret', '/\\evil'])
def test_api_rejects_untrusted_paths(monkeypatch, path):
    monkeypatch.setenv('TOKEN', 'secret')
    api = GitHub('owner/project', key_env='TOKEN')
    with pytest.raises(GitHubFailure, match='Invalid API path'):
        asyncio.run(api.request('GET', path))


def test_reconciliation_rejects_copied_review_from_other_user(tmp_path, server):
    server.drop = 'APPROVE'
    with pytest.raises(GitHubFailure):
        run(tmp_path, server, [CLEAN, CLEAN])
    server.reviews[-1]['user']['id'] = 99
    with pytest.raises(GitHubFailure, match='does not prove'):
        run(tmp_path, server, [], reconcile=True)



def test_operator_dismissal_reconciles_failed_approval_before_new_revision(tmp_path, server):
    server.drop = 'APPROVE'
    with pytest.raises(GitHubFailure):
        run(tmp_path, server, [CLEAN, CLEAN])
    server.reviews[-1]['state'] = 'DISMISSED'
    server.head = C
    server.drop = None
    assert run(tmp_path, server, [], reconcile=True)[0]['status'] == 'reconciled'
    assert run(tmp_path, server, [CLEAN, CLEAN])[0]['status'] == 'approved'
