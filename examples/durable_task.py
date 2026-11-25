"""Credential-free local state lifecycle; creates only a temporary private directory."""
import asyncio
from pathlib import Path
import tempfile

from harness4.adapters.sqlite_state import SQLiteState
from harness4.contracts import Event, ModelRef, TaskResult, TaskSpec, TaskStatus


async def main():
    with tempfile.TemporaryDirectory() as parent:
        directory = Path(parent) / 'state'
        with SQLiteState(directory) as state:
            task = await state.admit('demo', TaskSpec(agent_id='reviewer', goal='Demonstrate durable outputs', request_key='demo-1'), 'demo-policy')
            lease = await state.acquire('demo', task.task_id)
            await state.commit(lease, 0, TaskStatus.RUNNING, (), ())
            artifact = await state.put_artifact('demo', b'Deterministic demo output, not a model review.', 'text/plain')
            result = TaskResult(task_id=task.task_id, status=TaskStatus.SUCCEEDED, message='Demo finished',
                                artifacts=(artifact,), policy_hash=task.policy_hash,
                                model_ref=ModelRef(provider='fake', name='demo'), trace_id='demo-trace')
            event = Event(workspace_id='demo', task_id=task.task_id, event_id='completed', seq=1,
                          type='task.completed', timestamp='2026-11-24T00:00:00.000000Z')
            await state.commit(lease, 1, TaskStatus.SUCCEEDED, (event,), (), result=result)
        with SQLiteState(directory) as restarted:
            print((await restarted.result('demo', task.task_id)).model_dump_json(indent=2))
            assert await restarted.read_artifact('demo', artifact.artifact_id) == b'Deterministic demo output, not a model review.'


if __name__ == '__main__':
    asyncio.run(main())
