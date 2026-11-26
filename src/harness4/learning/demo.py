"""Credential-free lifecycle demonstration, permanently restricted to demo scope."""
import json

from ..contracts import UsageSummary, digest
from ..model_contracts import canonical_object
from ..ship import Review
from .contracts import Profile, ReviewInput, Episode, Feedback, Label, Membership, Dataset, Protocol
from .engine import run_cycle, review_case, Budget
from .store import LearningStore


class ScriptedBackend:
    evidence_class = 'scripted_demo'

    def __init__(self, profile):
        self.profile_hash, self.profile = digest(profile), profile

    async def __call__(self, system, payload):
        if 'development' in payload:
            answer = {'checklist': 'Preserve None; flag code that maps missing values to zero with `value or 0`.',
                      'hypothesis': 'Check missing-value coercion without flagging correct passthrough code.',
                      'evidence_refs': [x['evidence_id'] for x in payload['development']]}
        else:
            findings = []
            if 'Preserve None' in system:
                for path, text in payload['contents'].items():
                    if 'return value or 0' in text:
                        findings.append({'severity': 'high', 'path': path, 'line': 2,
                                         'title': 'Missing value becomes zero', 'explanation': 'None must remain missing.'})
            answer = {'summary': 'Scripted fixture review; not a quality measurement.', 'findings': findings}
        return {'text': json.dumps(answer), 'revision': self.profile.revision,
                'usage': UsageSummary(input_tokens=40, output_tokens=30)}


def seed(store):
    profile = Profile(model='fixture', base_url='https://example.invalid/v1', revision='fixture')
    store.initialize('demo/fixture', profile, mode='demo')
    members = []
    for index, (split, buggy) in enumerate([('dev', True), ('dev', False),
                                           ('target', True), ('target', True),
                                           ('anchor', False), ('anchor', False)]):
        path = f'src/example_{index}.py'
        text = 'def normalize(value):\n    return value' + (' or 0' if buggy else '') + f'\n# fixture {index}\n'
        input = ReviewInput(contents_json=canonical_object(json.dumps({path: text})), diff=f'+{text}')
        episode = Episode(repository='demo/fixture', revision=f'demo-{index}', policy_hash=store.config()['active'],
                          profile_hash=digest(profile), input=input, reviews=(Review(summary='fixture'), Review(summary='fixture')),
                          evidence_class='scripted_demo')
        episode_id = store.record_episode(episode)
        labels = (Label(path=path, line=2, severity='high'),) if buggy else ()
        feedback = Feedback(episode_id=episode_id, group=f'demo-source-{index}', labels=labels,
                            source='scripted_demo', source_ref='bundled-fixture-v1', consent=True, operator='demo')
        members.append(Membership(feedback_id=store.feedback(feedback), split=split))
    dataset = store.dataset(Dataset(name='demo-cohort-v1', cases=tuple(members)))
    return profile, dataset


async def demo(directory):
    with LearningStore(directory) as store:
        profile, dataset = seed(store)
        initial = store.config()['active']
        protocol = Protocol(max_candidates=1, max_calls=100)
        backend = ScriptedBackend(profile)
        result = await run_cycle(store, dataset, protocol, backend)
        if result['decision'] != 'eligible':
            return result
        approval = store.approve(result['report_id'], 'demo-operator')
        activated = store.promote(approval)
        _, _, fresh_episode = store.cases(dataset)[2]
        found, _ = await review_case(store.policy(), fresh_episode, Budget(protocol, profile, backend))
        rolled = store.rollback(initial, expected_generation=activated['generation'], operator='demo-operator', reason='Demonstrate rollback')
        old_found, _ = await review_case(store.policy(), fresh_episode, Budget(protocol, profile, backend))
        return {'evidence_class': 'scripted_demo', 'quality_claim': False, 'report_id': result['report_id'],
                'decision': result['decision'], 'baseline': initial, 'promoted': activated['active'],
                'fresh_review_finding_count': len(found), 'rollback_review_finding_count': len(old_found),
                'restored': rolled['active'], 'generation': rolled['generation'], 'budget': result['budget']}
