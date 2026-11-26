import asyncio
import json
import math
import sqlite3
import time

import httpx
import pytest
from pydantic import ValidationError

from harness4.contracts import digest, UsageSummary, PolicyBundle, Section
from harness4.learning.contracts import (Profile, ReviewInput, Episode, Feedback, Label, Dataset,
                                         Membership, Protocol, Proposal, review_system)
from harness4.learning.demo import seed, demo, ScriptedBackend
from harness4.learning.engine import run_cycle, release_gate
from harness4.learning.provider import LiveBackend
from harness4.learning.store import LearningStore, LearningError, encode
from harness4.model_contracts import canonical_object
from harness4.ship import Review


def run(store, dataset, backend=None, protocol=None):
    return asyncio.run(run_cycle(store, dataset, protocol or Protocol(max_candidates=1, max_calls=100),
                                 backend or ScriptedBackend(store.profile())))


@pytest.fixture
def seeded(tmp_path):
    with LearningStore(tmp_path / 'learning') as store:
        profile, dataset = seed(store)
        yield store, profile, dataset


def test_full_demo_has_real_activation_and_rollback_but_no_quality_claim(tmp_path):
    result = asyncio.run(demo(tmp_path / 'demo'))
    assert result['decision'] == 'eligible' and result['quality_claim'] is False
    assert result['evidence_class'] == 'scripted_demo'
    assert result['promoted'] != result['baseline'] == result['restored']
    assert result['fresh_review_finding_count'] == 1
    assert result['rollback_review_finding_count'] == 0
    with LearningStore(tmp_path / 'demo') as store:
        assert store.config()['active'] == result['baseline']
        assert store.config()['generation'] == 2
        assert [x['kind'] for x in store.status()['audit']][-2:] == ['promoted', 'rolled_back']


def test_candidate_not_active_before_approval_and_replay_blocked(seeded):
    store, _, dataset = seeded
    initial = store.config()
    result = run(store, dataset)
    assert store.config() == initial
    approval = store.approve(result['report_id'], 'operator')
    assert store.config() == initial
    after = store.promote(approval)
    assert after['active'] == result['candidate']
    with pytest.raises(LearningError, match='already used'):
        store.promote(approval)


def test_generation_prevents_aba_approval_replay(seeded):
    store, _, dataset = seeded
    result = run(store, dataset)
    a = store.approve(result['report_id'], 'alice')
    b = store.approve(result['report_id'], 'bob')
    store.promote(a)
    store.rollback(result['incumbent'], expected_generation=1, operator='alice', reason='test')
    with pytest.raises(LearningError, match='stale'):
        store.promote(b)


def test_expiry_checked_at_approval_and_activation(seeded, monkeypatch):
    store, _, dataset = seeded
    result = run(store, dataset)
    approval = store.approve(result['report_id'], 'operator')
    monkeypatch.setattr(time, 'time', lambda: result['expires'] + 1)
    with pytest.raises(LearningError, match='expired'):
        store.approve(result['report_id'], 'operator')
    with pytest.raises(LearningError, match='expired'):
        store.promote(approval)


def test_atomic_promotion_audit_failure_rolls_back_pointer_and_token(seeded):
    store, _, dataset = seeded
    result = run(store, dataset)
    approval = store.approve(result['report_id'], 'operator')
    store.db.execute("CREATE TRIGGER deny_promote BEFORE INSERT ON audit WHEN NEW.kind='promoted' BEGIN SELECT RAISE(ABORT, 'injected'); END")
    with pytest.raises(sqlite3.IntegrityError):
        store.promote(approval)
    assert store.config()['active'] == result['incumbent']
    assert store.db.execute('SELECT used FROM approvals WHERE id=?', (approval,)).fetchone()[0] == 0


def test_retract_rolls_back_and_revokes_dependent_policy(seeded):
    store, _, dataset = seeded
    result = run(store, dataset)
    store.promote(store.approve(result['report_id'], 'operator'))
    feedback = store.cases(dataset)[0][0].feedback_id
    store.retract(feedback, operator='operator', reason='Incorrect source label')
    assert store.config()['active'] == result['incumbent']
    with pytest.raises(LearningError, match='revoked'):
        store.policy(result['candidate'])
    with pytest.raises(LearningError, match='retracted'):
        store.cases(dataset)
    with pytest.raises(LearningError):
        store.rollback(result['candidate'], expected_generation=2, operator='operator', reason='cannot revive')


def test_policy_retraction_propagates_to_descendants(seeded):
    store, _, dataset = seeded
    result = run(store, dataset)
    child = store.put('policy', PolicyBundle(scope=store.policy().scope,
                        sections=(Section(name='review_checklist', text='descendant'),), model_profile=store.config()['profile']))
    store.put('candidate', {'policy': child, 'parent': result['candidate'], 'dataset': 'another-dataset'})
    store.retract(store.cases(dataset)[0][0].feedback_id, operator='operator', reason='bad label')
    with pytest.raises(LearningError, match='revoked'):
        store.policy(child)


def test_reused_holdout_cannot_be_retested_even_with_new_dataset_name(seeded):
    store, _, dataset = seeded
    assert run(store, dataset)['decision'] == 'eligible'
    copy = Dataset.model_validate_json(encode(store.get(dataset, 'dataset'))).model_copy(update={'name': 'renamed'})
    result = run(store, store.dataset(copy))
    assert result['decision'] == 'inconclusive'
    assert 'already consumed' in result['reason']


class Spy(ScriptedBackend):
    def __init__(self, profile):
        super().__init__(profile)
        self.calls = []

    async def __call__(self, system, payload):
        self.calls.append((system, payload))
        return await super().__call__(system, payload)


def test_sealed_inputs_and_labels_never_enter_proposer(seeded):
    store, profile, dataset = seeded
    spy = Spy(profile)
    assert run(store, dataset, spy)['decision'] == 'eligible'
    proposals = [p for _, p in spy.calls if 'development' in p]
    assert len(proposals) == 1
    text = encode(proposals)
    assert 'example_0.py' in text and 'example_1.py' in text
    assert all(f'example_{i}.py' not in text for i in range(2, 6))
    for _, payload in spy.calls:
        if 'development' not in payload:
            assert set(payload) == {'changed_files', 'contents', 'diff'}
            assert 'expected_findings' not in payload and 'group' not in payload


def test_crash_after_consuming_cohort_never_reuses_it(seeded):
    store, profile, dataset = seeded
    class Crash(Spy):
        async def __call__(self, system, payload):
            if 'example_2.py' in encode(payload):
                raise KeyboardInterrupt('simulated interruption')
            return await super().__call__(system, payload)
    with pytest.raises(KeyboardInterrupt):
        run(store, dataset, Crash(profile))
    status = store.status()
    report_id = status['cycles'][0]['report']
    assert store.report(report_id)['decision'] == 'inconclusive'
    with pytest.raises(LearningError):
        store.approve(report_id, 'operator')
    assert 'already consumed' in run(store, dataset)['reason']


@pytest.mark.parametrize('change', ['revision', 'invalid_output', 'transport', 'unknown_usage', 'tokens'])
def test_bad_evaluation_never_activates(seeded, change):
    store, profile, dataset = seeded
    class Broken(Spy):
        async def __call__(self, system, payload):
            result = await super().__call__(system, payload)
            if 'example_2.py' in encode(payload):
                if change == 'revision':
                    result['revision'] = 'drifted'
                if change == 'invalid_output':
                    result['text'] = '{"summary": "x", "grant": "approve"}'
                if change == 'transport':
                    raise RuntimeError('SECRET_DO_NOT_PRINT')
                if change == 'unknown_usage':
                    result['usage'] = UsageSummary()
                if change == 'tokens':
                    result['usage'] = UsageSummary(input_tokens=1_000_001, output_tokens=1)
            return result
    result = run(store, dataset, Broken(profile), Protocol(max_candidates=1, max_calls=100, max_total_tokens=1_000_000))
    assert result['decision'] != 'eligible'
    assert 'SECRET_DO_NOT_PRINT' not in encode(result)
    with pytest.raises(LearningError):
        store.approve(result['report_id'], 'operator')


def test_budget_too_small_makes_no_model_calls(seeded):
    store, profile, dataset = seeded
    backend = Spy(profile)
    with pytest.raises(LearningError, match='no model call'):
        run(store, dataset, backend, Protocol(max_calls=1))
    assert not backend.calls


def test_unknown_usage_recorded_without_fake_cost_when_no_total_cap(seeded):
    store, profile, dataset = seeded
    class Unknown(ScriptedBackend):
        async def __call__(self, system, payload):
            answer = await super().__call__(system, payload)
            answer['usage'] = UsageSummary()
            return answer
    result = run(store, dataset, Unknown(profile))
    assert result['decision'] == 'eligible'
    assert result['budget']['usage_incomplete'] is True
    assert result['budget']['known_tokens'] == 0


def test_harmful_candidate_fails_anchor_gate(seeded):
    store, profile, dataset = seeded
    class Overfit(ScriptedBackend):
        async def __call__(self, system, payload):
            answer = await super().__call__(system, payload)
            if 'Preserve None' in system and any(f'example_{i}.py' in encode(payload) for i in (4, 5)):
                path = next(iter(payload['contents']))
                answer['text'] = json.dumps({'summary': 'bad', 'findings': [{'severity': 'high', 'path': path,
                    'line': 2, 'title': 'false positive', 'explanation': 'incorrect'}]})
            return answer
    result = run(store, dataset, Overfit(profile))
    assert result['decision'] == 'rejected'
    assert result['metrics']['regressing_anchor_groups'] == 2
    with pytest.raises(LearningError):
        store.approve(result['report_id'], 'operator')


@pytest.mark.parametrize('variant', ['extra_permission', 'no_op', 'unknown_evidence', 'malformed'])
def test_invalid_proposals_are_archived_without_activation(seeded, variant):
    store, profile, dataset = seeded
    class BadProposal(ScriptedBackend):
        async def __call__(self, system, payload):
            answer = await super().__call__(system, payload)
            if 'development' in payload:
                proposal = json.loads(answer['text'])
                if variant == 'extra_permission':
                    proposal['allow_approval'] = True
                elif variant == 'no_op':
                    proposal['checklist'] = payload['incumbent_checklist']
                elif variant == 'unknown_evidence':
                    proposal['evidence_refs'] = ['held-out-id']
                answer['text'] = 'invalid' if variant == 'malformed' else json.dumps(proposal)
            return answer
    result = run(store, dataset, BadProposal(profile))
    assert result['decision'] == 'inconclusive' and result['archive'][0]['rejected']
    assert store.db.execute('SELECT count(*) FROM consumed').fetchone()[0] == 0


def test_group_overlap_and_duplicate_inputs_rejected(seeded):
    store, _, dataset = seeded
    cases = store.cases(dataset)
    member, feedback, episode = cases[2]
    conflicting = feedback.model_copy(update={'episode_id': store.record_episode(episode.model_copy(update={'revision': 'another'})),
                                             'group': cases[0][1].group})
    new_id = store.feedback(conflicting)
    original = Dataset.model_validate_json(encode(store.get(dataset, 'dataset')))
    changed = original.model_copy(update={'cases': (original.cases[0], original.cases[1],
               Membership(feedback_id=new_id, split='target'), *original.cases[3:])})
    with pytest.raises(LearningError, match='group crosses'):
        store.dataset(changed)
    duplicate = original.model_copy(update={'cases': (*original.cases, Membership(feedback_id=new_id, split='target'))})
    with pytest.raises(LearningError, match='Duplicate source'):
        store.dataset(duplicate)


def test_partition_history_prevents_holdout_moving_to_development(seeded):
    store, _, dataset = seeded
    original = Dataset.model_validate_json(encode(store.get(dataset, 'dataset')))
    members = list(original.cases)
    members[2] = members[2].model_copy(update={'split': 'dev'})
    with pytest.raises(LearningError, match='Previously exposed'):
        store.dataset(original.model_copy(update={'cases': tuple(members)}))


def test_feedback_rejects_out_of_revision_location_and_conflicting_labels(seeded):
    store, _, dataset = seeded
    _, feedback, _ = store.cases(dataset)[0]
    with pytest.raises(LearningError, match='finding location'):
        store.feedback(feedback.model_copy(update={'labels': (Label(path='elsewhere.py', line=1, severity='high'),)}))
    with pytest.raises(LearningError, match='Conflicting'):
        store.feedback(feedback.model_copy(update={'labels': ()}))
    assert store.feedback(feedback) == digest(feedback)


def test_demo_backend_cannot_evaluate_production(seeded):
    store, profile, dataset = seeded
    store.db.execute("UPDATE config SET mode='production'")
    with pytest.raises(LearningError, match='evidence class'):
        run(store, dataset, ScriptedBackend(profile), Protocol(max_candidates=1, max_calls=100, min_target_groups=1, min_anchor_groups=1))


def test_demo_report_cannot_approve_in_production(seeded):
    store, _, dataset = seeded
    result = run(store, dataset)
    store.db.execute("UPDATE config SET mode='production'")
    with pytest.raises(LearningError, match='ineligible'):
        store.approve(result['report_id'], 'operator')


def test_production_insufficient_groups_abstains_before_inference(seeded):
    store, profile, dataset = seeded
    store.db.execute("UPDATE config SET mode='production'")
    spy = Spy(profile)
    with pytest.raises(LearningError, match='Insufficient'):
        run(store, dataset, spy)
    assert not spy.calls


def gate_rows(n=100):
    return [dict(split='target', group=f't{i}', baseline=False, candidate=True) for i in range(n)] + [
        dict(split='anchor', group=f'a{i}', baseline=True, candidate=True) for i in range(n)]


def test_live_bounds_and_low_power_abstention():
    protocol = Protocol()
    decision, metrics, _ = release_gate(gate_rows(), protocol, mode='production')
    assert decision == 'eligible'
    assert metrics['target_gain_lower'] == pytest.approx(1 - math.sqrt(2 * math.log(40) / 100))
    assert metrics['anchor_risk_upper'] == pytest.approx(1 - 0.025 ** 0.01)
    assert release_gate(gate_rows(2), protocol, mode='production')[0] == 'inconclusive'
    rows = gate_rows()
    for row in rows[:90]:
        row['baseline'] = True
    assert release_gate(rows, protocol, mode='production')[0] == 'inconclusive'


def test_repeated_rows_do_not_count_as_independent_groups():
    rows = gate_rows(1) * 100
    decision, metrics, _ = release_gate(rows, Protocol(), mode='production')
    assert decision == 'inconclusive' and metrics['target_groups'] == 1


def test_forged_or_corrupt_report_never_approves(seeded):
    store, _, dataset = seeded
    result = run(store, dataset)
    fake = {k: v for k, v in result.items() if k != 'report_id'}
    fake['candidate'] = result['incumbent']
    forged = store.put('report', fake)
    with pytest.raises(LearningError, match='trusted evaluator receipt'):
        store.approve(forged, 'operator')
    store.db.execute('UPDATE objects SET payload=? WHERE id=?', ('{}', result['report_id']))
    with pytest.raises(LearningError, match='corrupt'):
        store.approve(result['report_id'], 'operator')


def test_rollback_rejects_unactivated_candidate_and_stale_generation(seeded):
    store, _, dataset = seeded
    result = run(store, dataset)
    with pytest.raises(LearningError, match='never active'):
        store.rollback(result['candidate'], expected_generation=0, operator='operator', reason='test')
    store.promote(store.approve(result['report_id'], 'operator'))
    with pytest.raises(LearningError, match='Stale'):
        store.rollback(result['incumbent'], expected_generation=0, operator='operator', reason='test')


def test_cli_demo_and_status(tmp_path, capsys):
    from harness4.cli import main
    root = tmp_path / 'demo'
    assert main(['learning', 'demo', '--state-dir', str(root)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['evidence_class'] == 'scripted_demo'
    assert main(['learning', 'status', '--state-dir', str(root)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status['active'] == result['baseline'] and status['generation'] == 2


@pytest.mark.parametrize('extra', ['allow_approval', 'tools', 'evaluator', 'base_url', 'max_calls'])
def test_proposal_cannot_expand_authority(extra):
    with pytest.raises(ValidationError):
        Proposal.model_validate_json(json.dumps({'checklist': 'x', 'hypothesis': 'x', 'evidence_refs': ['x'], extra: True}))


def test_live_backend_uses_no_tools_and_pins_revision(monkeypatch):
    monkeypatch.setenv('MODEL_KEY', 'PRIVATE_CREDENTIAL_CANARY')
    profile = Profile(model='pinned', base_url='https://model.invalid/v1', revision='pinned')
    def handler(request):
        body = json.loads(request.content)
        assert 'tools' not in body and 'PRIVATE_CREDENTIAL_CANARY' not in request.content.decode()
        return httpx.Response(200, json={'model': 'pinned', 'choices': [{'message': {'content': '{}'}, 'finish_reason': 'stop'}]})
    backend = LiveBackend(profile, key_env='MODEL_KEY', transport=httpx.MockTransport(handler))
    answer = asyncio.run(backend('system', {'input': 'x'}))
    assert answer['revision'] == 'pinned'
    assert answer['usage'].input_tokens is None


def test_production_gate_http_adapter_github_activation_and_rollback(tmp_path, monkeypatch):
    """202 synthetic groups exercise production mechanics, not measured model quality."""
    from argparse import Namespace
    from harness4 import github_cli
    from harness4.github import GitHub
    from test_github_workflow import Server, policy
    monkeypatch.setenv('MODEL_KEY', 'model-test')
    monkeypatch.setenv('WRITER', 'write')
    profile = Profile(model='pinned', base_url='https://model.invalid/v1', revision='pinned')
    observed = []
    def model_http(request):
        body = json.loads(request.content)
        assert 'tools' not in body
        system = body['messages'][0]['content']
        payload = json.loads(body['messages'][1]['content'])
        observed.append((system, payload))
        if 'development' in payload:
            answer = dict(checklist='Preserve None; flag missing-value coercion.', hypothesis='Retain missing values.',
                          evidence_refs=[p['evidence_id'] for p in payload['development']])
        else:
            findings = []
            if 'Preserve None' in system:
                for path, source in payload['contents'].items():
                    if 'return value or 0' in source:
                        findings.append(dict(path=path, line=2, severity='high', title='Missing value', explanation='None becomes zero.'))
            answer = dict(summary='Synthetic HTTP test.', findings=findings)
        return httpx.Response(200, json={'model': 'pinned', 'choices': [{'message': {'content': json.dumps(answer)},
            'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 40, 'completion_tokens': 30}})
    def backend(profile, **kwargs):
        return LiveBackend(profile, transport=httpx.MockTransport(model_http), **kwargs)
    root = tmp_path / 'learning'
    with LearningStore(root) as store:
        store.initialize('owner/project', profile)
        members = []
        specs = [('dev', True), ('dev', False)] + [('target', True)] * 100 + [('anchor', False)] * 100
        for i, (split, buggy) in enumerate(specs):
            path = f'src/source_{i}.py'
            source = 'def normalize(value):\n    return value' + (' or 0' if buggy else '') + '\n'
            ep = Episode(repository='owner/project', revision=f'revision-{i}', policy_hash=store.config()['active'],
                profile_hash=digest(profile), input=ReviewInput(contents_json=canonical_object(json.dumps({path: source})), diff='+' + source),
                reviews=(Review(summary='Synthetic'), Review(summary='Synthetic')), evidence_class='live')
            fid = store.feedback(Feedback(episode_id=store.record_episode(ep), group=f'independent-fixture-{i}',
                labels=(Label(path=path, line=2, severity='high'),) if buggy else (), source='deterministic_verified',
                source_ref='test fixture only', operator='test', consent=True))
            members.append(Membership(feedback_id=fid, split=split))
        ds = store.dataset(Dataset(name='synthetic-production-gate', cases=tuple(members)))
        result = run(store, ds, backend(profile, key_env='MODEL_KEY'), Protocol(max_candidates=1, max_calls=809))
        assert result['decision'] == 'eligible'
        assert result['budget']['attempted_calls'] == 809
        assert result['metrics']['target_groups'] == result['metrics']['anchor_groups'] == 100
        assert store.config()['active'] == result['incumbent']
        store.promote(store.approve(result['report_id'], 'test'))
    server = Server()
    server.source = 'def normalize(value):\n    return value or 0\n'
    monkeypatch.setattr(github_cli, 'LiveBackend', backend)
    monkeypatch.setattr(github_cli, 'GitHub', lambda repo, **kw: GitHub(repo, transport=httpx.MockTransport(server.handler), **kw))
    policy_path = tmp_path / 'policy.json'
    policy_path.write_text(policy(allow_repair=False).model_dump_json())
    args = Namespace(policy=policy_path, pr=1, state_dir=tmp_path / 'workflow', learning_dir=root,
        model=profile.model, base_url=profile.base_url, max_output_tokens=profile.max_output_tokens, timeout=profile.timeout,
        key_env='MODEL_KEY', github_key_env='WRITER', approval_key_env='APPROVER', write=True, approve=False,
        check_polls=1, poll_seconds=0, reconcile=False)
    active = asyncio.run(github_cli.execute(args))
    current = active['reports'][0]
    assert current['review_policy_hash'] == result['candidate']
    assert len(current['review']['findings']) == 1
    with LearningStore(root) as store:
        episode = store.get(current['learning_episode'], 'episode')
        assert episode['policy_hash'] == result['candidate']
        assert episode['revision'] == server.head
        store.rollback(result['incumbent'], expected_generation=1, operator='test', reason='Verify rollback')
    restored = asyncio.run(github_cli.execute(args))['reports'][0]
    assert restored['review_policy_hash'] == result['incumbent']
    assert restored['review']['findings'] == []
    assert len(server.writes) == 2
    assert all(body['event'] == 'COMMENT' for _, _, body in server.writes)
    assert result['candidate'] in server.writes[0][2]['body']
    assert result['incumbent'] in server.writes[1][2]['body']
    asyncio.run(github_cli.execute(args))
    assert len(server.writes) == 2  # Restart uses the same policy-bound receipt.


def test_hard_process_exit_preserves_consumed_cohort(tmp_path):
    import os
    import subprocess
    import sys
    root = tmp_path / 'crash'
    with LearningStore(root) as store:
        _, dataset = seed(store)
    code = '''
import asyncio, os, sys
from harness4.learning.store import LearningStore
from harness4.learning.demo import ScriptedBackend
from harness4.learning.contracts import Protocol
from harness4.learning.engine import run_cycle
class Kill(ScriptedBackend):
    async def __call__(self, system, payload):
        if 'src/example_2.py' in payload.get('contents', {}):
            os._exit(77)
        return await super().__call__(system, payload)
with LearningStore(sys.argv[1]) as store:
    asyncio.run(run_cycle(store, sys.argv[2], Protocol(max_candidates=1, max_calls=100), Kill(store.profile())))
'''
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    child = subprocess.run([sys.executable, '-c', code, str(root), dataset], env=env, capture_output=True, timeout=30)
    assert child.returncode == 77, child.stderr.decode()
    with LearningStore(root) as store:
        assert store.status()['cycles'][0]['status'] == 'running'
        assert store.status()['cycles'][0]['report'] is None
        assert store.db.execute('SELECT count(*) FROM consumed').fetchone()[0] == 8
        assert 'already consumed' in run(store, dataset)['reason']


def test_evaluation_enforces_production_combined_finding_bound(seeded):
    store, profile, dataset = seeded
    class Verbose(ScriptedBackend):
        async def __call__(self, system, payload):
            result = await super().__call__(system, payload)
            if 'src/example_2.py' in payload.get('contents', {}):
                result['text'] = json.dumps({'summary': 'too many', 'findings': [
                    {'path': 'src/example_2.py', 'line': 2, 'severity': 'high', 'title': str(i), 'explanation': 'defect'}
                    for i in range(41)]})
            return result
    result = run(store, dataset, Verbose(profile))
    assert result['decision'] == 'inconclusive'
    assert 'production finding bound' in result['reason']
