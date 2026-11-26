"""CLI wiring kept separate from local review and the pure coordinator."""
import json
from contextlib import ExitStack
from uuid import uuid4

from .adapters.sqlite_state import SQLiteState, StoreFailure
from .contracts import digest
from .github import GitHub, GitHubFailure
from .github_workflow import GitHubPolicy, WorkflowJournal, run_workflow
from .model_contracts import strict_object
from .provider import complete
from .ship import SYSTEM_PROMPT, Review
from .learning.store import LearningStore, LearningError, encode
from .learning.contracts import Episode, github_input, review_system
from .learning.provider import LiveBackend


async def execute(args):
    policy = GitHubPolicy.model_validate_json(json.dumps(strict_object(args.policy.read_text())))
    calls = []
    learning_backend = None

    async def model(system, payload):
        if learning_backend is not None:
            normalized = github_input(payload).payload() if system.startswith(SYSTEM_PROMPT) else payload
            answer = await learning_backend(system, normalized)
            text, usage = answer['text'], answer['usage']
        else:
            text, usage = await complete(base_url=args.base_url, model=args.model, key_env=args.key_env,
                                         system=system, prompt=json.dumps(payload), request_id=str(uuid4()),
                                         max_output_tokens=args.max_output_tokens, timeout=args.timeout)
        calls.append({'model': args.model, 'usage': usage.model_dump(mode='json')})
        return text

    try:
        with ExitStack() as stack:
            state = stack.enter_context(SQLiteState(args.state_dir))
            journal = WorkflowJournal(state, policy, args.pr)
            review_prompt, observer = SYSTEM_PROMPT, None
            if getattr(args, 'learning_dir', None):
                learning = stack.enter_context(LearningStore(args.learning_dir))
                config, profile = learning.config(), learning.profile()
                if (config['mode'] != 'production' or config['repository'] != policy.repository or
                        (profile.model, profile.base_url, profile.max_output_tokens, profile.timeout) !=
                        (args.model, args.base_url, args.max_output_tokens, args.timeout)):
                    raise LearningError('Learning scope/model settings do not match this GitHub run.')
                pinned = learning.policy()
                journal.review_policy_hash = digest(pinned)
                learning_backend = LiveBackend(profile, key_env=args.key_env)
                review_prompt = review_system(pinned)
                async def observer(payload, current):
                    learning.policy(digest(pinned))  # Reject a revoked pinned version.
                    return learning.record_episode(Episode(repository=policy.repository,
                        revision=current['head_sha'], policy_hash=digest(pinned), profile_hash=digest(profile),
                        input=github_input(payload), evidence_class='live', reviews=(
                            Review.model_validate_json(encode(current['review'])),
                            Review.model_validate_json(encode(current['verification'])))))
            try:
                report = await run_workflow(GitHub(policy.repository, key_env=args.github_key_env),
                    policy, args.pr, model, journal, write=args.write, approve=args.approve,
                    approver=GitHub(policy.repository, key_env=args.approval_key_env) if args.approve else None,
                    check_polls=args.check_polls, poll_seconds=args.poll_seconds, reconcile=args.reconcile,
                    review_prompt=review_prompt, observer=observer)
                report['model_calls'] = calls
                report['policy_digest'] = digest(policy)
                artifact = await state.put_artifact(policy.repository, json.dumps(report).encode(), 'application/json')
                report['artifact'] = artifact.model_dump(mode='json')
                return report
            finally:
                await journal.close()
    except (GitHubFailure, LearningError) as exc:
        return {'status': 'blocked', 'reason': str(exc), 'model_calls': calls}
    except StoreFailure as exc:
        return {'status': 'blocked', 'error': exc.error.model_dump(mode='json'), 'model_calls': calls}
    except (KeyError, TypeError, IndexError):
        return {'status': 'blocked', 'reason': 'Malformed GitHub evidence; no further action taken.', 'model_calls': calls}
