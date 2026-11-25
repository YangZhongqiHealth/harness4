import pytest
from pydantic import ValidationError
from harness4.contracts import *

@pytest.fixture
def base():
    return PolicyBundle(scope=Scope(workspace_id='demo',agent_id='normalizer',family='tables'),sections=(Section(name='nulls',text='Normalize missing values.'),),model_profile='fake@1')

def patch_for(base,**overrides):
    d=dict(base_policy_hash=digest(base),scope=base.scope,target='nulls',expected_component_hash=text_digest(base.sections[0].text),value='Preserve null values.',evidence_refs=('ep-1',),hypothesis='Avoid silent corruption.',optimizer_ref='reflection@1')
    d.update(overrides); return CandidatePatch(**d)

def test_contract_roundtrip(base):
    assert PolicyBundle.model_validate_json(base.model_dump_json())==base
    assert digest(PolicyBundle.model_validate_json(base.model_dump_json()))==digest(base)

def test_task_rejects_internal_authority():
    with pytest.raises(ValidationError):
        TaskSpec(agent_id='default',goal='go',request_key='1',policy_hash='override')

def test_request_fingerprint_changes():
    a=TaskSpec(agent_id='default',goal='go',request_key='1')
    b=TaskSpec(agent_id='default',goal='different',request_key='1')
    assert digest(a)!=digest(b)

def test_state_pin_and_version():
    s=TaskSnapshot(workspace_id='w',task_id='t',policy_hash='p')
    r=transition(s,TaskStatus.RUNNING,0)
    assert r.policy_hash=='p' and r.state_version==1
    with pytest.raises(ValueError,match='stale'): transition(r,TaskStatus.SUCCEEDED,0)
    finished=transition(r,TaskStatus.SUCCEEDED,1)
    with pytest.raises(ValueError,match='illegal'): transition(finished,TaskStatus.QUEUED,2)

def test_wait_cannot_finish_directly():
    s=TaskSnapshot(workspace_id='w',task_id='t',policy_hash='p',status=TaskStatus.WAITING_EVENT)
    with pytest.raises(ValueError): transition(s,TaskStatus.SUCCEEDED,0)

def test_patch_changes_only_named_section(base):
    p=apply_patch(base,patch_for(base),allowed_sections=frozenset({'nulls'}))
    assert p.sections[0].text=='Preserve null values.' and p.scope==base.scope
    assert digest(p)!=digest(base) and base.sections[0].text!='Preserve null values.'

@pytest.mark.parametrize('override',[{'base_policy_hash':'old'},{'expected_component_hash':'old'},{'value':'Normalize missing values.'},{'target':'unknown'}])
def test_patch_rejects_invalid(base,override):
    with pytest.raises(ValueError): apply_patch(base,patch_for(base,**override),allowed_sections=frozenset({'nulls'}))

def test_patch_scope_and_grant(base):
    with pytest.raises(ValueError): apply_patch(base,patch_for(base,scope=Scope(workspace_id='other',agent_id='normalizer',family='tables')),allowed_sections=frozenset({'nulls'}))
    with pytest.raises(ValueError): apply_patch(base,patch_for(base),allowed_sections=frozenset())

def test_forbid_evaluator_changes(base):
    with pytest.raises(ValidationError): patch_for(base,surface='evaluator')

def report(**kwargs):
    d=dict(incumbent_hash='old',candidate_hash='new',expected_case_ids=('1','2'),cases=(PairedCase(case_id='1',split='target',baseline_pass=False,candidate_pass=True),PairedCase(case_id='2',split='anchor',baseline_pass=True,candidate_pass=True)),budget_met=True)
    d.update(kwargs);return DemoScorecard(**d)

def gate(r,scope='demo',base='old'):
    return demo_gate(r,expected_incumbent=base,expected_candidate='new',release_scope=scope)

def test_demo_only():
    assert gate(report())==GateDecision.ELIGIBLE_DEMO
    assert gate(report(),'production')==GateDecision.REJECTED
    assert gate(report(),base='stale')==GateDecision.REJECTED

@pytest.mark.parametrize('override',[{'budget_met':False},{'hard_violations':('unauthorized tool',)}])
def test_hard_checks(override):
    assert gate(report(**override))==GateDecision.REJECTED

def test_missing_cases_inconclusive():
    assert gate(report(cases=()))==GateDecision.INCONCLUSIVE

def test_anchor_regression():
    r=report(); a=r.cases[1].model_copy(update={'candidate_pass':False})
    assert gate(report(cases=(r.cases[0],a)))==GateDecision.REJECTED
