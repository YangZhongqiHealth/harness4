"""State transaction, crash recovery, namespace and private artifact tests."""
import asyncio
from hashlib import sha256
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from harness4.adapters.sqlite_state import SQLiteState, StoreFailure
from harness4.contracts import ActionReceipt, EffectIntent, Event, TaskSpec, TaskStatus, text_digest


def run(coroutine):
    return asyncio.run(coroutine)


def spec(key='request-1', goal='Review the PR'):
    return TaskSpec(agent_id='reviewer',goal=goal,request_key=key)


def admitted(store,key='request-1'):
    return run(store.admit('w',spec(key),'policy-v1'))


def event(snapshot, seq=1, event_id='event-1', **overrides):
    args=dict(workspace_id=snapshot.workspace_id,task_id=snapshot.task_id,seq=seq,event_id=event_id,type='task.started',timestamp='2026-11-24T00:00:00.000000Z')
    args.update(overrides)
    return Event(**args)


def intent(operation_id='op-1', **overrides):
    args=dict(operation_id=operation_id,intent_hash=text_digest('intent'),request_ref='request:1')
    args.update(overrides)
    return EffectIntent(**args)


@pytest.fixture
def store(tmp_path):
    with SQLiteState(tmp_path/'private') as state:
        yield state


def test_migration_wal_and_restart(tmp_path):
    directory=tmp_path/'private'
    with SQLiteState(directory) as state:
        original=admitted(state)
        assert state._db.execute('PRAGMA journal_mode').fetchone()[0]=='wal'
        assert state._db.execute('PRAGMA foreign_keys').fetchone()[0]==1
        assert state._db.execute('PRAGMA user_version').fetchone()[0]==1
    with SQLiteState(directory) as state:
        assert run(state.load('w',original.task_id))==original


def test_idempotent_admission_and_policy_pin(store):
    first=admitted(store)
    second=run(store.admit('w',spec(),'new-active-policy'))
    assert first==second and second.policy_hash=='policy-v1'
    with pytest.raises(StoreFailure,match='different input'):
        run(store.admit('w',spec(goal='changed goal'),'policy-v1'))
    other=run(store.admit('other',spec(),'policy-v1'))
    assert other.task_id!=first.task_id


@pytest.mark.parametrize('lookup', ['load','events','steps','pending_operations'])
def test_task_namespace_at_every_read(store,lookup):
    task=admitted(store)
    with pytest.raises(StoreFailure):
        run(getattr(store,lookup)('other',task.task_id))


def test_atomic_transition_events_steps_and_cursor(store):
    task=admitted(store)
    lease=run(store.acquire('w',task.task_id))
    after=run(store.commit(lease,0,TaskStatus.RUNNING,(event(task),),()))
    assert after.state_version==1 and after.policy_hash==task.policy_hash
    after=run(store.commit(lease,1,TaskStatus.SUCCEEDED,(event(task,seq=2,event_id='event-2',type='task.completed'),),()))
    assert after.state_version==2
    assert [s.seq for s in run(store.steps('w',task.task_id))]==[1,2]
    assert [e.seq for e in run(store.events('w',task.task_id,1))]==[2]
    assert run(store.events('w',task.task_id,2))==()
    with pytest.raises(StoreFailure):
        run(store.commit(lease,2,TaskStatus.QUEUED,(),()))
    with pytest.raises(StoreFailure):
        run(store.acquire('w',task.task_id))


def test_stale_version_and_stale_fence(store):
    task=admitted(store)
    first=run(store.acquire('w',task.task_id))
    with pytest.raises(StoreFailure,match='active run'):
        run(store.acquire('w',task.task_id))
    run(store.commit(first,0,TaskStatus.RUNNING,(),()))
    with pytest.raises(StoreFailure):
        run(store.commit(first,0,TaskStatus.SUCCEEDED,(),()))
    run(store.release(first))
    second=run(store.acquire('w',task.task_id))
    assert second.fence==first.fence+1 and second.run_id!=first.run_id
    with pytest.raises(StoreFailure,match='fence'):
        run(store.commit(first,1,TaskStatus.SUCCEEDED,(),()))
    assert run(store.commit(second,1,TaskStatus.SUCCEEDED,(),())).status==TaskStatus.SUCCEEDED


def test_transaction_rolls_back_all_rows_on_late_failure(store):
    task=admitted(store)
    lease=run(store.acquire('w',task.task_id))
    store._db.execute("CREATE TEMP TRIGGER inject_failure BEFORE INSERT ON steps BEGIN SELECT RAISE(ABORT,'fault'); END")
    with pytest.raises(StoreFailure):
        run(store.commit(lease,0,TaskStatus.RUNNING,(event(task),),(intent(),)))
    assert run(store.load('w',task.task_id))==task
    assert not run(store.events('w',task.task_id))
    assert not run(store.steps('w',task.task_id))
    assert not run(store.pending_operations('w',task.task_id))
    store._db.execute('DROP TRIGGER inject_failure')
    assert run(store.commit(lease,0,TaskStatus.RUNNING,(event(task),),(intent(),))).state_version==1


@pytest.mark.parametrize('changes', [{'workspace_id':'other'},{'task_id':'other'},{'seq':2}])
def test_event_scope_and_sequence_rollback(store,changes):
    task=admitted(store); lease=run(store.acquire('w',task.task_id))
    with pytest.raises(StoreFailure):
        run(store.commit(lease,0,TaskStatus.RUNNING,(event(task,**changes),),()))
    assert run(store.load('w',task.task_id))==task


def test_event_duplicate_id_rollback(store):
    task=admitted(store); lease=run(store.acquire('w',task.task_id))
    run(store.commit(lease,0,TaskStatus.RUNNING,(event(task),),()))
    with pytest.raises(StoreFailure):
        run(store.commit(lease,1,TaskStatus.SUCCEEDED,(event(task,seq=2),),()))
    assert run(store.load('w',task.task_id)).state_version==1
    assert len(run(store.events('w',task.task_id)))==1


def test_intent_and_receipt_are_stable_and_scoped(store):
    task=admitted(store); lease=run(store.acquire('w',task.task_id))
    run(store.commit(lease,0,TaskStatus.RUNNING,(),(intent(),)))
    assert run(store.operation('w','op-1')).status=='pending'
    with pytest.raises(StoreFailure):
        run(store.operation('other','op-1'))
    with pytest.raises(StoreFailure):
        run(store.commit(lease,1,TaskStatus.QUEUED,(),(intent(request_ref='different'),)))
    receipt=ActionReceipt(operation_id='op-1',status='succeeded',summary='Artifact created')
    committed=run(store.record_receipt(lease,receipt))
    assert run(store.record_receipt(lease,receipt))==committed
    with pytest.raises(StoreFailure):
        run(store.record_receipt(lease,ActionReceipt(operation_id='op-1',status='failed',summary='replacement')))
    assert not run(store.pending_operations('w',task.task_id))
    assert run(store.commit(lease,1,TaskStatus.SUCCEEDED,(),())).status==TaskStatus.SUCCEEDED


def test_pending_effect_cannot_silently_succeed(store):
    task=admitted(store); lease=run(store.acquire('w',task.task_id))
    run(store.commit(lease,0,TaskStatus.RUNNING,(),(intent(),)))
    with pytest.raises(StoreFailure,match='reconciliation'):
        run(store.commit(lease,1,TaskStatus.SUCCEEDED,(),()))
    run(store.commit(lease,1,TaskStatus.RECONCILING,(),()))
    assert run(store.commit(lease,2,TaskStatus.UNKNOWN_EFFECT,(),())).status==TaskStatus.UNKNOWN_EFFECT
    assert run(store.operation('w','op-1')).status=='pending'


def test_operation_cannot_move_between_tasks(store):
    task=admitted(store); lease=run(store.acquire('w',task.task_id))
    run(store.commit(lease,0,TaskStatus.RUNNING,(),(intent(),)))
    other=admitted(store,'second'); other_lease=run(store.acquire('w',other.task_id))
    with pytest.raises(StoreFailure):
        run(store.commit(other_lease,0,TaskStatus.RUNNING,(),(intent(),)))
    with pytest.raises(StoreFailure):
        run(store.record_receipt(other_lease,ActionReceipt(operation_id='op-1',status='succeeded',summary='wrong task')))


def test_restart_fences_old_run_and_keeps_pending_intent(tmp_path):
    directory=tmp_path/'private'
    with SQLiteState(directory) as state:
        task=admitted(state); old=run(state.acquire('w',task.task_id))
        run(state.commit(old,0,TaskStatus.RUNNING,(),(intent(),)))
    with SQLiteState(directory) as state:
        new=run(state.acquire('w',task.task_id))
        assert new.fence>old.fence
        assert len(run(state.pending_operations('w',task.task_id)))==1
        with pytest.raises(StoreFailure):
            run(state.record_receipt(old,ActionReceipt(operation_id='op-1',status='succeeded',summary='stale worker')))


def test_second_coordinator_refused_and_close_releases_lock(tmp_path):
    directory=tmp_path/'private'
    first=SQLiteState(directory)
    try:
        with pytest.raises(StoreFailure,match='coordinator'):
            SQLiteState(directory)
    finally:
        first.close()
    with SQLiteState(directory):
        pass


def test_process_crash_releases_lock_and_preserves_committed_state(tmp_path):
    directory=tmp_path/'private'
    script='''
import asyncio,os,sys
from harness4.adapters.sqlite_state import SQLiteState
from harness4.contracts import TaskSpec
store=SQLiteState(sys.argv[1])
asyncio.run(store.admit('w',TaskSpec(agent_id='a',goal='go',request_key='r'),'p'))
os._exit(0)
'''
    env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')}
    subprocess.run([sys.executable,'-c',script,str(directory)],env=env,check=True)
    with SQLiteState(directory) as state:
        task=run(state.admit('w',TaskSpec(agent_id='a',goal='go',request_key='r'),'changed-policy'))
        assert task.policy_hash=='p'


def test_artifacts_digest_restart_and_workspace_isolation(tmp_path):
    directory=tmp_path/'private'
    with SQLiteState(directory) as state:
        ref=run(state.put_artifact('w',b'hello','text/plain'))
        assert ref.digest==text_digest('hello') and ref.size_bytes==5
        assert run(state.read_artifact('w',ref.artifact_id))==b'hello'
        with pytest.raises(StoreFailure):
            run(state.read_artifact('other',ref.artifact_id))
    with SQLiteState(directory) as state:
        assert run(state.read_artifact('w',ref.artifact_id))==b'hello'


def test_corrupted_artifact_fails_closed(store):
    ref=run(store.put_artifact('w',b'hello','text/plain'))
    path=store._artifact_directory('w')/ref.digest.split(':')[1]
    path.write_bytes(b'changed')
    with pytest.raises(StoreFailure,match='digest'):
        run(store.read_artifact('w',ref.artifact_id))
    with pytest.raises(StoreFailure,match='digest'):
        run(store.put_artifact('w',b'hello','text/plain'))


def test_orphan_cleanup_preserves_referenced_shared_content(store):
    ref=run(store.put_artifact('w',b'hello','text/plain'))
    second=run(store.put_artifact('w',b'hello','text/plain'))
    assert ref.artifact_id!=second.artifact_id
    directory=store._artifact_directory('w')
    orphan=sha256(b'orphan').hexdigest()
    (directory/orphan).write_bytes(b'orphan')
    (directory/'.tmp-abandoned').write_bytes(b'incomplete')
    (directory/'unrelated').write_bytes(b'preserve')
    assert run(store.sweep_orphans('w',min_age_seconds=0))==tuple(sorted([orphan,'.tmp-abandoned']))
    assert run(store.read_artifact('w',ref.artifact_id))==b'hello'
    assert run(store.read_artifact('w',second.artifact_id))==b'hello'
    assert (directory/'unrelated').exists()


def test_failed_artifact_reference_commit_leaves_collectible_orphan(store):
    store._db.execute("CREATE TEMP TRIGGER inject_failure BEFORE INSERT ON artifacts BEGIN SELECT RAISE(ABORT,'fault'); END")
    with pytest.raises(StoreFailure):
        run(store.put_artifact('w',b'orphan','text/plain'))
    store._db.execute('DROP TRIGGER inject_failure')
    assert run(store.sweep_orphans('w',min_age_seconds=0))==(sha256(b'orphan').hexdigest(),)


@pytest.mark.skipif(os.name=='nt',reason='POSIX permission and symlink checks')
def test_private_paths_and_artifact_symlinks(tmp_path):
    public=tmp_path/'public'; public.mkdir(mode=0o755)
    with pytest.raises(StoreFailure):
        SQLiteState(public)
    external=tmp_path/'external'; external.mkdir(mode=0o700)
    link=tmp_path/'link'; link.symlink_to(external,target_is_directory=True)
    with pytest.raises(StoreFailure):
        SQLiteState(link)
    with SQLiteState(tmp_path/'private') as state:
        ref=run(state.put_artifact('w',b'hello','text/plain'))
        artifact=state._artifact_directory('w')/ref.digest.split(':')[1]
        artifact.unlink(); artifact.symlink_to(tmp_path/'secret')
        with pytest.raises(StoreFailure):
            run(state.read_artifact('w',ref.artifact_id))


def test_newer_schema_is_not_modified(tmp_path):
    directory=tmp_path/'private'
    with SQLiteState(directory) as state:
        state._db.execute('PRAGMA user_version=99')
    with pytest.raises(StoreFailure,match='schema'):
        SQLiteState(directory)
    db=sqlite3.connect(directory/'state.sqlite3')
    assert db.execute('PRAGMA user_version').fetchone()[0]==99
    db.close()


def test_result_and_terminal_transition_are_atomic_and_persist(tmp_path):
    from harness4.contracts import ModelRef,TaskResult
    directory=tmp_path/'private'
    with SQLiteState(directory) as state:
        task=admitted(state); lease=run(state.acquire('w',task.task_id))
        run(state.commit(lease,0,TaskStatus.RUNNING,(),()))
        ref=run(state.put_artifact('w',b'report','text/plain'))
        result=TaskResult(task_id=task.task_id,status=TaskStatus.SUCCEEDED,message='Done',artifacts=(ref,),policy_hash=task.policy_hash,model_ref=ModelRef(provider='fake',name='test'),trace_id='trace-1')
        state._db.execute("CREATE TEMP TRIGGER inject_failure BEFORE INSERT ON steps BEGIN SELECT RAISE(ABORT,'fault'); END")
        with pytest.raises(StoreFailure):
            run(state.commit(lease,1,TaskStatus.SUCCEEDED,(event(task,type='task.completed'),),(),result=result))
        assert run(state.result('w',task.task_id)) is None
        assert run(state.load('w',task.task_id)).status==TaskStatus.RUNNING
        state._db.execute('DROP TRIGGER inject_failure')
        run(state.commit(lease,1,TaskStatus.SUCCEEDED,(event(task,type='task.completed'),),(),result=result))
    with SQLiteState(directory) as state:
        assert run(state.result('w',task.task_id))==result
        assert run(state.task_spec('w',task.task_id))==spec()
        with pytest.raises(StoreFailure):
            run(state.result('other',task.task_id))


def test_result_cannot_use_other_workspace_artifact(store):
    from harness4.contracts import ModelRef,TaskResult
    task=admitted(store); lease=run(store.acquire('w',task.task_id))
    run(store.commit(lease,0,TaskStatus.RUNNING,(),()))
    ref=run(store.put_artifact('other',b'private','text/plain'))
    result=TaskResult(task_id=task.task_id,status=TaskStatus.SUCCEEDED,artifacts=(ref,),policy_hash=task.policy_hash,model_ref=ModelRef(provider='fake',name='test'),trace_id='trace-1')
    with pytest.raises(StoreFailure):
        run(store.commit(lease,1,TaskStatus.SUCCEEDED,(),(),result=result))
    assert run(store.load('w',task.task_id)).state_version==1


def test_canonicalizer_version_mismatch_rejected(tmp_path):
    directory=tmp_path/'private'
    with SQLiteState(directory) as state:
        state._db.execute("UPDATE metadata SET value='999' WHERE key='canonicalizer_version'")
    with pytest.raises(StoreFailure,match='canonicalizer'):
        SQLiteState(directory)


@pytest.mark.skipif(os.name=='nt',reason='POSIX symlink boundary')
def test_symlinked_artifact_parent_cannot_escape(store,tmp_path):
    root=store.root/'artifacts'
    root.rmdir()
    external=tmp_path/'external'; external.mkdir(mode=0o700)
    root.symlink_to(external,target_is_directory=True)
    with pytest.raises(StoreFailure):
        run(store.put_artifact('w',b'escape','text/plain'))
    assert list(external.iterdir())==[]


@pytest.mark.skipif(os.name=='nt',reason='POSIX FIFO test')
def test_artifact_fifo_is_rejected_without_blocking(store):
    ref=run(store.put_artifact('w',b'hello','text/plain'))
    target=store._artifact_directory('w')/ref.digest.split(':')[1]
    target.unlink(); os.mkfifo(target)
    with pytest.raises(StoreFailure,match='regular'):
        run(store.read_artifact('w',ref.artifact_id))


def test_process_crash_rolls_back_uncommitted_update(tmp_path):
    directory=tmp_path/'private'
    with SQLiteState(directory) as state:
        original=admitted(state)
    script='''
import os,sys
from harness4.adapters.sqlite_state import SQLiteState
store=SQLiteState(sys.argv[1])
store._db.execute('BEGIN IMMEDIATE')
store._db.execute("UPDATE tasks SET snapshot='uncommitted-corruption'")
os._exit(0)
'''
    env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')}
    subprocess.run([sys.executable,'-c',script,str(directory)],env=env,check=True)
    with SQLiteState(directory) as state:
        assert run(state.load('w',original.task_id))==original


@pytest.mark.parametrize('age',[float('nan'),float('inf'),-1])
def test_orphan_cleanup_rejects_invalid_age(store,age):
    with pytest.raises(StoreFailure):
        run(store.sweep_orphans('w',min_age_seconds=age))


def test_result_cannot_fabricate_receipts(store):
    from harness4.contracts import ModelRef,TaskResult
    task=admitted(store); lease=run(store.acquire('w',task.task_id))
    run(store.commit(lease,0,TaskStatus.RUNNING,(),()))
    receipt=ActionReceipt(operation_id='never-executed',status='succeeded',summary='Fabricated action')
    result=TaskResult(task_id=task.task_id,status=TaskStatus.SUCCEEDED,action_receipts=(receipt,),policy_hash=task.policy_hash,model_ref=ModelRef(provider='fake',name='test'),trace_id='trace-1')
    with pytest.raises(StoreFailure):
        run(store.commit(lease,1,TaskStatus.SUCCEEDED,(),(),result=result))
    assert run(store.load('w',task.task_id)).status==TaskStatus.RUNNING
