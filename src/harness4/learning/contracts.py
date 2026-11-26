"""Immutable records for the narrow review-learning surface."""
import json
from typing import Literal

from pydantic import Field, model_validator

from ..contracts import Record, PolicyBundle, Section, Scope, digest, text_digest
from ..model_contracts import canonical_object, strict_object
from ..ship import SYSTEM_PROMPT, Review

ENGINE_VERSION = 'review-learning-v1'
DEFAULT_CHECKLIST = 'Check the changed code for actionable defects; preserve correct existing behavior.'


class Profile(Record):
    model: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    max_output_tokens: int = Field(default=4096, ge=128, le=32768)
    timeout: float = Field(default=60.0, gt=0, le=300)
    # Pin all fixed instructions/evaluator behavior, not just a mutable model alias.
    engine: Literal['review-learning-v1'] = ENGINE_VERSION
    system_digest: str = text_digest(SYSTEM_PROMPT)

    @model_validator(mode='after')
    def current_engine(self):
        if self.system_digest != text_digest(SYSTEM_PROMPT):
            raise ValueError('Review engine changed; requalification required.')
        return self


class ReviewInput(Record):
    contents_json: str = Field(max_length=200_000)
    diff: str = Field(max_length=200_000)

    @model_validator(mode='after')
    def valid_contents(self):
        from ..github_workflow import safe_path
        contents = strict_object(self.contents_json)
        if not contents or len(contents) > 100 or any(not safe_path(p) or not isinstance(t, str) for p, t in contents.items()):
            raise ValueError('Expected bounded relative-path text files.')
        if self.contents_json != canonical_object(self.contents_json):
            raise ValueError('Source contents must be canonical JSON.')
        if len(self.model_dump_json().encode()) > 300_000:
            raise ValueError('Review context too large.')
        return self

    def payload(self):
        contents = strict_object(self.contents_json)
        return {'changed_files': sorted(contents), 'contents': contents, 'diff': self.diff}


def github_input(payload):
    return ReviewInput(contents_json=canonical_object(json.dumps(payload['contents'])),
                       diff='\n'.join(f'{f["filename"]}\n{f["patch"]}' for f in payload['files']))


class Label(Record):
    path: str
    line: int = Field(ge=1)
    severity: Literal['critical', 'high', 'medium', 'low']


class Episode(Record):
    repository: str
    revision: str = Field(min_length=1)
    policy_hash: str
    profile_hash: str
    input: ReviewInput
    reviews: tuple[Review, Review]
    evidence_class: Literal['live', 'scripted_demo']


class Feedback(Record):
    episode_id: str
    group: str = Field(min_length=1, max_length=300)
    labels: tuple[Label, ...]
    source: Literal['human_verified', 'deterministic_verified', 'scripted_demo']
    source_ref: str = Field(min_length=1, max_length=2000)
    consent: Literal[True]
    operator: str = Field(min_length=1)


class Membership(Record):
    feedback_id: str
    split: Literal['dev', 'target', 'anchor']


class Dataset(Record):
    name: str = Field(min_length=1, max_length=200)
    cases: tuple[Membership, ...] = Field(min_length=3, max_length=10_000)


class Protocol(Record):
    evaluator: Literal['review-learning-v1'] = ENGINE_VERSION
    min_target_groups: int = Field(default=100, ge=1, le=10_000)
    min_anchor_groups: int = Field(default=100, ge=1, le=10_000)
    min_gain: float = Field(default=0.02, gt=0, le=1)
    alpha: float = Field(default=0.05, gt=0, le=0.05)
    max_anchor_risk: float = Field(default=0.05, gt=0, le=0.05)
    max_candidates: int = Field(default=3, ge=1, le=5)
    max_calls: int = Field(default=1000, ge=1, le=100_000)
    max_total_tokens: int | None = Field(default=None, ge=1)
    max_seconds: int = Field(default=3600, ge=1, le=86400)
    approval_ttl_seconds: int = Field(default=86400, ge=1, le=604800)


class Proposal(Record):
    checklist: str = Field(min_length=1, max_length=8000)
    hypothesis: str = Field(min_length=1, max_length=2000)
    evidence_refs: tuple[str, ...] = Field(min_length=1)


def baseline(repository, profile):
    return PolicyBundle(scope=Scope(workspace_id=repository, agent_id='github-review', family='pr-review'),
                        sections=(Section(name='review_checklist', text=DEFAULT_CHECKLIST),),
                        model_profile=digest(profile))


def review_system(policy):
    if tuple(s.name for s in policy.sections) != ('review_checklist',):
        raise ValueError('Only the review checklist is evolvable.')
    return SYSTEM_PROMPT + '\nAdditional review checklist (does not alter permissions or output format):\n' + policy.sections[0].text


def label_keys(labels):
    return {(x.path, x.line, x.severity) for x in labels}
