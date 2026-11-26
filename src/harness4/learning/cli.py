"""Explicit operator commands; no background learning or silent paid inference."""
import getpass
import json
from pathlib import Path

from ..adapters.sqlite_state import StoreFailure
from ..model_contracts import strict_object
from .contracts import Profile, Feedback, Label, Dataset, Protocol
from .engine import run_cycle
from .provider import LiveBackend
from .store import LearningStore, LearningError, encode


def add_parser(commands):
    learning = commands.add_parser('learning', help='Verify, activate and roll back learned review policies.')
    actions = learning.add_subparsers(dest='learning_action', required=True)
    for name in ('init', 'feedback', 'dataset', 'run', 'status', 'inspect', 'approve', 'promote', 'rollback', 'retract', 'demo'):
        cmd = actions.add_parser(name)
        cmd.add_argument('--state-dir', type=Path, required=True)
        if name == 'init':
            cmd.add_argument('--repository', required=True)
            cmd.add_argument('--profile', type=Path, required=True)
        elif name == 'feedback':
            cmd.add_argument('--episode', required=True)
            cmd.add_argument('--labels', type=Path, required=True, help='JSON object with labels array.')
            cmd.add_argument('--group', required=True, help='Independent source group, never an arbitrary row ID.')
            cmd.add_argument('--source', choices=['human_verified', 'deterministic_verified'], default='human_verified')
            cmd.add_argument('--source-ref', required=True)
            cmd.add_argument('--consent', action='store_true', required=True)
        elif name == 'dataset':
            cmd.add_argument('--manifest', type=Path, required=True)
        elif name == 'run':
            cmd.add_argument('--dataset', required=True)
            cmd.add_argument('--protocol', type=Path, required=True)
            cmd.add_argument('--live', action='store_true', required=True, help='Authorize paid calls within the supplied protocol budget.')
            cmd.add_argument('--key-env', default='H4_MODEL_KEY')
        elif name == 'inspect':
            cmd.add_argument('--id', required=True)
            cmd.add_argument('--kind', choices=['report', 'policy', 'candidate'], default='report')
        elif name == 'approve':
            cmd.add_argument('--report', required=True)
        elif name == 'promote':
            cmd.add_argument('--approval', required=True)
        elif name == 'rollback':
            cmd.add_argument('--target', required=True)
            cmd.add_argument('--expected-generation', type=int, required=True)
            cmd.add_argument('--reason', required=True)
        elif name == 'retract':
            cmd.add_argument('--feedback', required=True)
            cmd.add_argument('--reason', required=True)


def read_object(path):
    with path.open('rb') as file:
        data = file.read(2_000_001)
    if len(data) > 2_000_000:
        raise LearningError('Learning input exceeds file-size limit.')
    return strict_object(data.decode('utf-8'))


def read(path, cls):
    return cls.model_validate_json(encode(read_object(path)))


async def execute(args):
    try:
        if args.learning_action == 'demo':
            from .demo import demo
            return await demo(args.state_dir)
        with LearningStore(args.state_dir) as store:
            action = args.learning_action
            operator = getpass.getuser()  # Local OS owner, not a model-supplied principal.
            if action == 'init':
                return store.initialize(args.repository, read(args.profile, Profile))
            if action == 'feedback':
                data = read_object(args.labels)
                if set(data) != {'labels'}:
                    raise LearningError('Expected a labels-only object.')
                labels = tuple(Label.model_validate_json(encode(x)) for x in data['labels'])
                return {'feedback_id': store.feedback(Feedback(episode_id=args.episode, group=args.group,
                    labels=labels, source=args.source, source_ref=args.source_ref, consent=args.consent, operator=operator))}
            if action == 'dataset':
                return {'dataset_id': store.dataset(read(args.manifest, Dataset))}
            if action == 'run':
                return await run_cycle(store, args.dataset, read(args.protocol, Protocol),
                                       LiveBackend(store.profile(), key_env=args.key_env))
            if action == 'status':
                return store.status()
            if action == 'inspect':
                return store.report(args.id) if args.kind == 'report' else store.get(args.id, args.kind)
            if action == 'approve':
                return {'approval_id': store.approve(args.report, operator)}
            if action == 'promote':
                return store.promote(args.approval)
            if action == 'rollback':
                return store.rollback(args.target, expected_generation=args.expected_generation, operator=operator, reason=args.reason)
            if action == 'retract':
                return store.retract(args.feedback, operator=operator, reason=args.reason)
    except LearningError as exc:
        return {'status': 'blocked', 'reason': str(exc)}
    except StoreFailure as exc:
        return {'status': 'blocked', 'reason': exc.error.message}
