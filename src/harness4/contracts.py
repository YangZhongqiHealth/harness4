"""P0 contract subset. Pure validation only; no authorization or I/O guarantees."""
from __future__ import annotations
from enum import StrEnum
from hashlib import sha256
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)
    schema_version: Literal[1] = 1

class TaskStatus(StrEnum):
    QUEUED='queued'; RUNNING='running'; WAITING_INPUT='waiting_input'
    WAITING_EVENT='waiting_event'; WAITING_APPROVAL='waiting_approval'
    RETRY_DELAY='retry_delay'; RECONCILING='reconciling'; CANCELLING='cancelling'
    SUCCEEDED='succeeded'; PARTIAL='partial'; FAILED='failed'
    CANCELLED='cancelled'; UNKNOWN_EFFECT='unknown_effect'

TERMINAL=frozenset({TaskStatus.SUCCEEDED,TaskStatus.PARTIAL,TaskStatus.FAILED,TaskStatus.CANCELLED,TaskStatus.UNKNOWN_EFFECT})
EDGES={
    TaskStatus.QUEUED: {TaskStatus.RUNNING,TaskStatus.CANCELLED,TaskStatus.FAILED},
    TaskStatus.RUNNING: {TaskStatus.QUEUED,TaskStatus.WAITING_INPUT,TaskStatus.WAITING_EVENT,TaskStatus.WAITING_APPROVAL,TaskStatus.RETRY_DELAY,TaskStatus.RECONCILING,TaskStatus.CANCELLING,TaskStatus.SUCCEEDED,TaskStatus.PARTIAL,TaskStatus.FAILED},
    TaskStatus.RECONCILING: {TaskStatus.QUEUED,TaskStatus.UNKNOWN_EFFECT,TaskStatus.CANCELLED},
    TaskStatus.CANCELLING: {TaskStatus.CANCELLED,TaskStatus.RECONCILING},
    **{s:{TaskStatus.QUEUED,TaskStatus.CANCELLED,TaskStatus.FAILED,TaskStatus.PARTIAL} for s in (TaskStatus.WAITING_INPUT,TaskStatus.WAITING_EVENT,TaskStatus.WAITING_APPROVAL,TaskStatus.RETRY_DELAY)}
}

def canonical_bytes(record: Record) -> bytes:
    return json.dumps(record.model_dump(mode='json'),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')

def digest(record: Record) -> str:
    return 'sha256:'+sha256(canonical_bytes(record)).hexdigest()

def text_digest(text: str) -> str:
    return 'sha256:'+sha256(text.encode('utf-8')).hexdigest()

class TaskSpec(Record):
    agent_id: str = Field(min_length=1)
    session_id: str|None = None
    goal: str = Field(min_length=1,max_length=100_000)
    inputs: tuple[str,...] = ()
    resources: tuple[str,...] = ()
    requested_capabilities: tuple[str,...] = ()
    outcome_spec_ref: str|None = None
    output_schema_ref: str|None = None
    request_key: str = Field(min_length=1,max_length=128)
    # Server must resolve these references and authority, not trust client values.

class TaskSnapshot(Record):
    workspace_id: str
    task_id: str
    policy_hash: str
    status: TaskStatus = TaskStatus.QUEUED
    state_version: int = Field(default=0,ge=0)

def transition(snapshot: TaskSnapshot, target: TaskStatus, expected_version: int) -> TaskSnapshot:
    """Pure edge/CAS precheck only. DB transaction and fencing still required."""
    if expected_version != snapshot.state_version:
        raise ValueError('CONFLICT: stale state version')
    if target not in EDGES.get(snapshot.status,set()):
        raise ValueError('CONFLICT: illegal state transition')
    return snapshot.model_copy(update={'status':target,'state_version':snapshot.state_version+1})

class Scope(Record):
    workspace_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    family: str = Field(min_length=1)

class Section(Record):
    name: str = Field(pattern=r'^[a-z][a-z0-9_]{0,63}$')
    text: str = Field(min_length=1,max_length=20_000)

class PolicyBundle(Record):
    scope: Scope
    sections: tuple[Section,...] = Field(min_length=1)
    model_profile: str = Field(min_length=1)
    @model_validator(mode='after')
    def unique_sorted_sections(self):
        names=[s.name for s in self.sections]
        if names!=sorted(set(names)):
            raise ValueError('sections must be unique and sorted by name')
        return self

class CandidatePatch(Record):
    base_policy_hash: str
    scope: Scope
    surface: Literal['instructions']='instructions'
    op: Literal['replace_section']='replace_section'
    target: str = Field(pattern=r'^[a-z][a-z0-9_]{0,63}$')
    expected_component_hash: str
    value: str = Field(min_length=1,max_length=20_000)
    evidence_refs: tuple[str,...] = Field(min_length=1)
    hypothesis: str = Field(min_length=1,max_length=2_000)
    optimizer_ref: str = Field(min_length=1)

def apply_patch(base: PolicyBundle, patch: CandidatePatch, *, allowed_sections: frozenset[str]) -> PolicyBundle:
    """Structural patch only. Caller must verify evidence, permissions and safety."""
    if digest(base)!=patch.base_policy_hash or base.scope!=patch.scope:
        raise ValueError('STALE_CANDIDATE: parent or scope mismatch')
    if patch.target not in allowed_sections:
        raise ValueError('NOT_AUTHORIZED: section not evolvable')
    sections=[]; found=False
    for s in base.sections:
        if s.name==patch.target:
            found=True
            if text_digest(s.text)!=patch.expected_component_hash:
                raise ValueError('STALE_CANDIDATE: component mismatch')
            if s.text==patch.value:
                raise ValueError('INVALID_INPUT: no-op patch')
            s=Section(name=s.name,text=patch.value)
        sections.append(s)
    if not found:
        raise ValueError('INVALID_INPUT: section not present')
    return PolicyBundle(scope=base.scope,sections=tuple(sections),model_profile=base.model_profile)

class PairedCase(Record):
    case_id: str=Field(min_length=1)
    split: Literal['target','anchor']
    baseline_pass: bool
    candidate_pass: bool

class DemoScorecard(Record):
    evidence_class: Literal['scripted_demo']='scripted_demo'
    incumbent_hash: str
    candidate_hash: str
    expected_case_ids: tuple[str,...] = Field(min_length=1)
    cases: tuple[PairedCase,...]
    hard_violations: tuple[str,...]=()
    budget_met: bool

class GateDecision(StrEnum):
    ELIGIBLE_DEMO='eligible_demo'; REJECTED='rejected'; INCONCLUSIVE='inconclusive'

def demo_gate(report: DemoScorecard, *, expected_incumbent: str, expected_candidate: str, release_scope: Literal['demo','production']) -> GateDecision:
    """Fixture arithmetic, NOT trusted promotion/verification. No live eligibility."""
    if release_scope!='demo' or report.hard_violations or not report.budget_met:
        return GateDecision.REJECTED
    if report.incumbent_hash!=expected_incumbent or report.candidate_hash!=expected_candidate or expected_incumbent==expected_candidate:
        return GateDecision.REJECTED
    expected=report.expected_case_ids; actual=[c.case_id for c in report.cases]
    if len(set(expected))!=len(expected) or len(set(actual))!=len(actual) or set(expected)!=set(actual):
        return GateDecision.INCONCLUSIVE
    target=[c for c in report.cases if c.split=='target']; anchor=[c for c in report.cases if c.split=='anchor']
    if not target or not anchor:
        return GateDecision.INCONCLUSIVE
    gain=lambda rows:sum(int(c.candidate_pass)-int(c.baseline_pass) for c in rows)
    if gain(anchor)<0 or gain(target)<1:
        return GateDecision.REJECTED
    return GateDecision.ELIGIBLE_DEMO


class ErrorCode(StrEnum):
    INVALID_INPUT = 'INVALID_INPUT'
    UNSUPPORTED_CAPABILITY = 'UNSUPPORTED_CAPABILITY'
    NOT_AUTHORIZED = 'NOT_AUTHORIZED'
    CONFLICT = 'CONFLICT'
    BUDGET_EXHAUSTED = 'BUDGET_EXHAUSTED'
    TIMEOUT = 'TIMEOUT'
    TRANSIENT_PROVIDER = 'TRANSIENT_PROVIDER'
    INVALID_MODEL_OUTPUT = 'INVALID_MODEL_OUTPUT'
    UNKNOWN_EFFECT = 'UNKNOWN_EFFECT'
    INSUFFICIENT_EVIDENCE = 'INSUFFICIENT_EVIDENCE'
    STALE_CANDIDATE = 'STALE_CANDIDATE'


class DomainError(Record):
    """Safe boundary error; adapters must redact before constructing this record."""
    code: ErrorCode
    message: str = Field(min_length=1)
    retryable: bool
    correlation_id: str = Field(min_length=1)


class Principal(Record):
    workspace_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)


class ModelRef(Record):
    provider: str = Field(min_length=1)
    name: str = Field(min_length=1)


class UsageSummary(Record):
    # None means unknown, including when the provider omits usage.
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cost_microcurrency: int | None = Field(default=None, ge=0)
    estimated: bool = False


class ArtifactRef(Record):
    artifact_id: str = Field(min_length=1)
    digest: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    mime_type: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    retrieval_ref: str = Field(min_length=1)
    provenance_refs: tuple[str, ...] = ()
    retention_ref: str = Field(min_length=1)


class ActionReceipt(Record):
    operation_id: str = Field(min_length=1)
    status: Literal['succeeded', 'failed', 'unknown_effect']
    summary: str = Field(min_length=1)
    artifact_refs: tuple[ArtifactRef, ...] = ()


class VerificationReport(Record):
    status: Literal['not_evaluated', 'verified', 'failed', 'inconclusive']
    evidence_refs: tuple[str, ...] = ()


class PendingRequest(Record):
    request_id: str = Field(min_length=1)
    kind: Literal['input', 'event', 'approval', 'reconciliation']
    message: str = Field(min_length=1)


class TaskResult(Record):
    task_id: str = Field(min_length=1)
    session_id: str | None = None
    status: TaskStatus
    message: str | None = None
    artifacts: tuple[ArtifactRef, ...] = ()
    action_receipts: tuple[ActionReceipt, ...] = ()
    verification: VerificationReport = Field(default_factory=lambda: VerificationReport(status='not_evaluated'))
    pending: tuple[PendingRequest, ...] = ()
    usage: UsageSummary = Field(default_factory=UsageSummary)
    policy_hash: str = Field(min_length=1)
    model_ref: ModelRef
    trace_id: str = Field(min_length=1)


class Event(Record):
    """Durable display event. Payload references point to separately scoped records."""
    workspace_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    seq: int = Field(ge=1)
    type: Literal['task.started', 'message.delta', 'tool.started', 'tool.completed',
                  'approval.required', 'task.waiting', 'task.completed', 'task.failed',
                  'task.cancelled', 'learning.completed']
    timestamp: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$')
    message: str | None = None
    payload_refs: tuple[str, ...] = ()

    @model_validator(mode='after')
    def valid_timestamp(self):
        from datetime import datetime
        datetime.strptime(self.timestamp, '%Y-%m-%dT%H:%M:%S.%fZ')
        return self


class AdmissionReceipt(Record):
    task_id: str = Field(min_length=1)
    status: TaskStatus
    stream_cursor: int = Field(default=0, ge=0)


class TaskView(Record):
    snapshot: TaskSnapshot
    result: TaskResult | None = None


class Lease(Record):
    workspace_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    fence: int = Field(ge=1)


class EffectIntent(Record):
    operation_id: str = Field(min_length=1)
    intent_hash: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    request_ref: str = Field(min_length=1)


class PolicyView(Record):
    policy_hash: str = Field(min_length=1)
    bundle: PolicyBundle

    @model_validator(mode='after')
    def matching_hash(self):
        if self.policy_hash != digest(self.bundle):
            raise ValueError('policy hash does not match bundle')
        return self
