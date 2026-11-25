"""Single-coordinator SQLite WAL state and content-addressed private artifacts.

This repository checks namespace, versions and local run fences. It is not the
application's authorization service and performs no provider or tool calls.
"""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import os
import math
from pathlib import Path
import re
import sqlite3
import stat
import tempfile
import time
from uuid import uuid4

from ..contracts import (
    ActionReceipt, ArtifactRef, DomainError, EffectIntent, ErrorCode, Event,
    Lease, TaskResult, TaskSnapshot, TaskSpec, TaskStatus, TERMINAL, digest, transition as apply_transition,
)
from ..state_contracts import OperationView, StoredStep

SCHEMA_VERSION = 1
MIGRATION_1 = (
    "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "INSERT INTO metadata VALUES('canonicalizer_version','1')",
    'CREATE TABLE tasks (workspace TEXT NOT NULL, task TEXT NOT NULL, snapshot TEXT NOT NULL, spec TEXT NOT NULL, fence INTEGER NOT NULL DEFAULT 0, run TEXT, owner TEXT, PRIMARY KEY(workspace,task))',
    'CREATE TABLE requests (workspace TEXT NOT NULL, request_key TEXT NOT NULL, fingerprint TEXT NOT NULL, task TEXT NOT NULL, PRIMARY KEY(workspace,request_key), FOREIGN KEY(workspace,task) REFERENCES tasks(workspace,task))',
    'CREATE TABLE steps (workspace TEXT NOT NULL, task TEXT NOT NULL, seq INTEGER NOT NULL, snapshot TEXT NOT NULL, PRIMARY KEY(workspace,task,seq), FOREIGN KEY(workspace,task) REFERENCES tasks(workspace,task))',
    'CREATE TABLE events (workspace TEXT NOT NULL, task TEXT NOT NULL, seq INTEGER NOT NULL, event_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(workspace,task,seq), UNIQUE(workspace,event_id), FOREIGN KEY(workspace,task) REFERENCES tasks(workspace,task))',
    'CREATE TABLE operations (workspace TEXT NOT NULL, operation_id TEXT NOT NULL, task TEXT NOT NULL, intent TEXT NOT NULL, receipt TEXT, PRIMARY KEY(workspace,operation_id), FOREIGN KEY(workspace,task) REFERENCES tasks(workspace,task))',
    'CREATE TABLE results (workspace TEXT NOT NULL, task TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(workspace,task), FOREIGN KEY(workspace,task) REFERENCES tasks(workspace,task))',
    'CREATE TABLE artifacts (workspace TEXT NOT NULL, artifact TEXT NOT NULL, digest TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(workspace,artifact))',
)


class StoreFailure(Exception):
    def __init__(self, code: ErrorCode, message: str):
        self.error = DomainError(code=code, message=message, retryable=False, correlation_id=str(uuid4()))
        super().__init__(message)


def _private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or path.is_symlink():
        raise StoreFailure(ErrorCode.NOT_AUTHORIZED, 'State path must be a real private directory.')
    if os.name == 'posix' and (info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise StoreFailure(ErrorCode.NOT_AUTHORIZED, 'State directory must be owned by this user with mode 0700.')


def _private_file(path: Path) -> int:
    if path.is_symlink():
        raise StoreFailure(ErrorCode.NOT_AUTHORIZED, 'State files cannot be symbolic links.')
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or (os.name == 'posix' and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
        os.close(fd)
        raise StoreFailure(ErrorCode.NOT_AUTHORIZED, 'State files must be private regular files.')
    return fd


class SQLiteState:
    def __init__(self, directory: str | Path):
        self.root = Path(directory).absolute()
        _private_directory(self.root)
        self._lock = _private_file(self.root / 'coordinator.lock')
        self._db = None
        self._closed = False
        self.owner = str(uuid4())
        try:
            if os.name == 'nt':
                import msvcrt
                if os.fstat(self._lock).st_size == 0:
                    os.write(self._lock, b'0')
                os.lseek(self._lock, 0, os.SEEK_SET)
                msvcrt.locking(self._lock, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self._lock)
            self._closed = True
            raise StoreFailure(ErrorCode.CONFLICT, 'Another coordinator owns this state directory.') from None
        try:
            path = self.root / 'state.sqlite3'
            os.close(_private_file(path))
            # SQLite sidecars must not redirect writes through preexisting links.
            for suffix in ('-wal', '-shm', '-journal'):
                sidecar = Path(str(path) + suffix)
                if sidecar.exists() or sidecar.is_symlink():
                    os.close(_private_file(sidecar))
            self._db = sqlite3.connect(path, isolation_level=None, timeout=1)
            self._db.row_factory = sqlite3.Row
            self._db.execute('PRAGMA foreign_keys=ON')
            self._db.execute('PRAGMA busy_timeout=1000')
            self._db.execute('PRAGMA journal_mode=WAL')
            self._db.execute('PRAGMA synchronous=FULL')
            with self._transaction():
                version = self._db.execute('PRAGMA user_version').fetchone()[0]
                if version not in (0, SCHEMA_VERSION):
                    raise StoreFailure(ErrorCode.INVALID_INPUT, 'Unsupported state database schema version.')
                if version == 0:
                    for statement in MIGRATION_1:
                        self._db.execute(statement)
                    self._db.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
                canonicalizer = self._db.execute("SELECT value FROM metadata WHERE key='canonicalizer_version'").fetchone()
                if canonicalizer is None or canonicalizer[0] != '1':
                    raise StoreFailure(ErrorCode.INVALID_INPUT, 'Unsupported canonicalizer version.')
            _private_directory(self.root / 'artifacts')
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        if self._db is not None:
            self._db.close()
        if os.name == 'nt':
            import msvcrt
            os.lseek(self._lock, 0, os.SEEK_SET)
            msvcrt.locking(self._lock, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self._lock, fcntl.LOCK_UN)
        os.close(self._lock)
        self._closed = True

    def _ensure_open(self):
        if self._closed:
            raise StoreFailure(ErrorCode.CONFLICT, 'State repository is closed.')

    @contextmanager
    def _transaction(self):
        self._ensure_open()
        try:
            self._db.execute('BEGIN IMMEDIATE')
            yield
            self._db.execute('COMMIT')
        except BaseException as exc:
            if self._db.in_transaction:
                self._db.execute('ROLLBACK')
            if isinstance(exc, sqlite3.Error):
                raise StoreFailure(ErrorCode.CONFLICT, 'Conflicting state, event or operation identity.') from None
            raise

    @staticmethod
    def _workspace(workspace_id: str):
        if not isinstance(workspace_id, str) or not workspace_id:
            raise StoreFailure(ErrorCode.INVALID_INPUT, 'A workspace namespace is required.')

    def _task(self, workspace_id: str, task_id: str):
        self._ensure_open()
        self._workspace(workspace_id)
        row = self._db.execute('SELECT * FROM tasks WHERE workspace=? AND task=?', (workspace_id, task_id)).fetchone()
        if row is None:
            raise StoreFailure(ErrorCode.NOT_AUTHORIZED, 'Task is unavailable in this workspace.')
        return row

    def _fenced(self, lease: Lease):
        row = self._task(lease.workspace_id, lease.task_id)
        if row['owner'] != self.owner or (row['run'], row['fence']) != (lease.run_id, lease.fence):
            raise StoreFailure(ErrorCode.CONFLICT, 'Stale or released run fence.')
        return row

    async def admit(self, workspace_id: str, spec: TaskSpec, policy_hash: str) -> TaskSnapshot:
        """Trusted caller must resolve policy and grants before invoking this method."""
        self._workspace(workspace_id)
        if not policy_hash:
            raise StoreFailure(ErrorCode.INVALID_INPUT, 'A resolved policy hash is required.')
        with self._transaction():
            prior = self._db.execute('SELECT * FROM requests WHERE workspace=? AND request_key=?', (workspace_id, spec.request_key)).fetchone()
            if prior:
                if prior['fingerprint'] != digest(spec):
                    raise StoreFailure(ErrorCode.CONFLICT, 'Request key was reused with different input.')
                # An active-policy change never changes an already admitted task's pin.
                return TaskSnapshot.model_validate_json(self._task(workspace_id, prior['task'])['snapshot'])
            snapshot = TaskSnapshot(workspace_id=workspace_id, task_id=str(uuid4()), policy_hash=policy_hash)
            self._db.execute('INSERT INTO tasks(workspace,task,snapshot,spec) VALUES(?,?,?,?)',
                             (workspace_id, snapshot.task_id, snapshot.model_dump_json(), spec.model_dump_json()))
            self._db.execute('INSERT INTO requests VALUES(?,?,?,?)', (workspace_id, spec.request_key, digest(spec), snapshot.task_id))
            return snapshot

    async def load(self, workspace_id: str, task_id: str) -> TaskSnapshot:
        return TaskSnapshot.model_validate_json(self._task(workspace_id, task_id)['snapshot'])

    async def task_spec(self, workspace_id: str, task_id: str) -> TaskSpec:
        return TaskSpec.model_validate_json(self._task(workspace_id, task_id)['spec'])

    async def result(self, workspace_id: str, task_id: str) -> TaskResult | None:
        self._task(workspace_id, task_id)
        row = self._db.execute('SELECT payload FROM results WHERE workspace=? AND task=?', (workspace_id, task_id)).fetchone()
        return TaskResult.model_validate_json(row['payload']) if row else None

    async def acquire(self, workspace_id: str, task_id: str) -> Lease:
        with self._transaction():
            row = self._task(workspace_id, task_id)
            if TaskSnapshot.model_validate_json(row['snapshot']).status in TERMINAL:
                raise StoreFailure(ErrorCode.CONFLICT, 'Terminal tasks cannot acquire a run.')
            if row['owner'] == self.owner:
                raise StoreFailure(ErrorCode.CONFLICT, 'Task already has an active run.')
            # A prior coordinator cannot still run: the exclusive OS lock is held.
            # Pending operations survive takeover and must be reconciled by the kernel.
            lease = Lease(workspace_id=workspace_id, task_id=task_id, run_id=str(uuid4()), fence=row['fence'] + 1)
            self._db.execute('UPDATE tasks SET run=?,fence=?,owner=? WHERE workspace=? AND task=?',
                             (lease.run_id, lease.fence, self.owner, workspace_id, task_id))
            return lease

    async def release(self, lease: Lease) -> None:
        with self._transaction():
            self._fenced(lease)
            self._db.execute('UPDATE tasks SET run=NULL,owner=NULL WHERE workspace=? AND task=?', (lease.workspace_id, lease.task_id))

    async def commit(self, lease: Lease, expected_version: int, transition: TaskStatus,
                     events: tuple[Event, ...], effects: tuple[EffectIntent, ...],
                     *, result: TaskResult | None = None) -> TaskSnapshot:
        if type(expected_version) is not int or expected_version < 0 or not isinstance(transition, TaskStatus):
            raise StoreFailure(ErrorCode.INVALID_INPUT, 'Expected version and transition must be typed values.')
        with self._transaction():
            row = self._fenced(lease)
            before = TaskSnapshot.model_validate_json(row['snapshot'])
            try:
                after = apply_transition(before, transition, expected_version)
            except ValueError:
                raise StoreFailure(ErrorCode.CONFLICT, 'Stale version or illegal task transition.') from None
            cursor = self._db.execute('SELECT COALESCE(MAX(seq),0) FROM events WHERE workspace=? AND task=?',
                                      (lease.workspace_id, lease.task_id)).fetchone()[0]
            for offset, event in enumerate(events, 1):
                if (event.workspace_id, event.task_id, event.seq) != (lease.workspace_id, lease.task_id, cursor + offset):
                    raise StoreFailure(ErrorCode.CONFLICT, 'Event namespace or sequence does not match the task.')
                self._db.execute('INSERT INTO events VALUES(?,?,?,?,?)',
                                 (event.workspace_id, event.task_id, event.seq, event.event_id, event.model_dump_json()))
            for intent in effects:
                existing = self._db.execute('SELECT task,intent FROM operations WHERE workspace=? AND operation_id=?',
                                            (lease.workspace_id, intent.operation_id)).fetchone()
                if existing:
                    if existing['task'] != lease.task_id or EffectIntent.model_validate_json(existing['intent']) != intent:
                        raise StoreFailure(ErrorCode.CONFLICT, 'Operation ID was reused with different intent.')
                else:
                    self._db.execute('INSERT INTO operations VALUES(?,?,?,?,NULL)',
                                     (lease.workspace_id, intent.operation_id, lease.task_id, intent.model_dump_json()))
            pending = self._db.execute('SELECT COUNT(*) FROM operations WHERE workspace=? AND task=? AND receipt IS NULL',
                                       (lease.workspace_id, lease.task_id)).fetchone()[0]
            if pending and transition in TERMINAL and transition != TaskStatus.UNKNOWN_EFFECT:
                raise StoreFailure(ErrorCode.CONFLICT, 'Unresolved operations require reconciliation before termination.')
            if result is not None:
                spec = TaskSpec.model_validate_json(row['spec'])
                if (after.status not in TERMINAL or result.task_id != after.task_id or result.status != after.status
                        or result.policy_hash != after.policy_hash or result.session_id != spec.session_id):
                    raise StoreFailure(ErrorCode.CONFLICT, 'Result does not match the terminal task and pinned policy.')
                for receipt in result.action_receipts:
                    recorded = self._operation(lease.workspace_id, receipt.operation_id)
                    if recorded.task_id != lease.task_id or recorded.receipt != receipt:
                        raise StoreFailure(ErrorCode.CONFLICT, 'Result receipt does not match the committed operation.')
                refs = result.artifacts + tuple(ref for receipt in result.action_receipts for ref in receipt.artifact_refs)
                for ref in refs:
                    artifact = self._db.execute('SELECT payload FROM artifacts WHERE workspace=? AND artifact=?',
                                                (lease.workspace_id, ref.artifact_id)).fetchone()
                    if artifact is None or ArtifactRef.model_validate_json(artifact['payload']) != ref:
                        raise StoreFailure(ErrorCode.NOT_AUTHORIZED, 'Result references an unavailable artifact.')
                self._db.execute('INSERT INTO results VALUES(?,?,?)', (lease.workspace_id, lease.task_id, result.model_dump_json()))
            self._db.execute('INSERT INTO steps VALUES(?,?,?,?)',
                             (lease.workspace_id, lease.task_id, after.state_version, after.model_dump_json()))
            self._db.execute('UPDATE tasks SET snapshot=? WHERE workspace=? AND task=?',
                             (after.model_dump_json(), lease.workspace_id, lease.task_id))
            return after

    async def events(self, workspace_id: str, task_id: str, after_seq: int = 0) -> tuple[Event, ...]:
        self._task(workspace_id, task_id)
        if type(after_seq) is not int or after_seq < 0:
            raise StoreFailure(ErrorCode.INVALID_INPUT, 'Event cursor must be nonnegative.')
        rows = self._db.execute('SELECT payload FROM events WHERE workspace=? AND task=? AND seq>? ORDER BY seq',
                                (workspace_id, task_id, after_seq)).fetchall()
        return tuple(Event.model_validate_json(row['payload']) for row in rows)

    async def steps(self, workspace_id: str, task_id: str) -> tuple[StoredStep, ...]:
        self._task(workspace_id, task_id)
        rows = self._db.execute('SELECT seq,snapshot FROM steps WHERE workspace=? AND task=? ORDER BY seq', (workspace_id, task_id)).fetchall()
        return tuple(StoredStep(seq=row['seq'], snapshot=TaskSnapshot.model_validate_json(row['snapshot'])) for row in rows)

    def _operation(self, workspace_id: str, operation_id: str) -> OperationView:
        self._ensure_open()
        self._workspace(workspace_id)
        row = self._db.execute('SELECT * FROM operations WHERE workspace=? AND operation_id=?', (workspace_id, operation_id)).fetchone()
        if row is None:
            raise StoreFailure(ErrorCode.NOT_AUTHORIZED, 'Operation is unavailable in this workspace.')
        receipt = ActionReceipt.model_validate_json(row['receipt']) if row['receipt'] else None
        return OperationView(workspace_id=workspace_id, task_id=row['task'], intent=EffectIntent.model_validate_json(row['intent']),
                             receipt=receipt, status=receipt.status if receipt else 'pending')

    async def operation(self, workspace_id: str, operation_id: str) -> OperationView:
        return self._operation(workspace_id, operation_id)

    async def pending_operations(self, workspace_id: str, task_id: str) -> tuple[OperationView, ...]:
        self._task(workspace_id, task_id)
        rows = self._db.execute('SELECT operation_id FROM operations WHERE workspace=? AND task=? AND receipt IS NULL ORDER BY operation_id',
                                (workspace_id, task_id)).fetchall()
        return tuple(self._operation(workspace_id, row['operation_id']) for row in rows)

    async def record_receipt(self, lease: Lease, receipt: ActionReceipt) -> OperationView:
        with self._transaction():
            row = self._fenced(lease)
            if TaskSnapshot.model_validate_json(row['snapshot']).status in TERMINAL:
                raise StoreFailure(ErrorCode.CONFLICT, 'Terminal task receipts require explicit reconciliation.')
            current = self._operation(lease.workspace_id, receipt.operation_id)
            if current.task_id != lease.task_id:
                raise StoreFailure(ErrorCode.NOT_AUTHORIZED, 'Operation does not belong to this task.')
            if current.receipt:
                if current.receipt != receipt:
                    raise StoreFailure(ErrorCode.CONFLICT, 'A committed receipt cannot be replaced.')
                return current
            self._db.execute('UPDATE operations SET receipt=? WHERE workspace=? AND operation_id=?',
                             (receipt.model_dump_json(), lease.workspace_id, receipt.operation_id))
            return self._operation(lease.workspace_id, receipt.operation_id)

    def _artifact_directory(self, workspace_id: str) -> Path:
        self._ensure_open()
        self._workspace(workspace_id)
        _private_directory(self.root)
        _private_directory(self.root / 'artifacts')
        directory = self.root / 'artifacts' / sha256(workspace_id.encode()).hexdigest()
        _private_directory(directory)
        return directory

    async def put_artifact(self, workspace_id: str, data: bytes, mime_type: str, *, provenance_refs: tuple[str, ...] = ()) -> ArtifactRef:
        directory = self._artifact_directory(workspace_id)
        fingerprint = sha256(data).hexdigest()
        reference = ArtifactRef(artifact_id=str(uuid4()), digest='sha256:' + fingerprint, mime_type=mime_type,
                                size_bytes=len(data), retrieval_ref='artifact:' + fingerprint,
                                provenance_refs=provenance_refs, retention_ref='workspace-private')
        destination = directory / fingerprint
        if destination.exists() or destination.is_symlink():
            self._read_bytes(destination, reference)
        else:
            fd, temporary = tempfile.mkstemp(prefix='.tmp-', dir=directory)
            try:
                with os.fdopen(fd, 'wb') as output:
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, destination)
                if os.name == 'posix':
                    directory_fd = os.open(directory, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        # If this transaction fails, the committed file is a collectible orphan.
        with self._transaction():
            self._db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',
                             (workspace_id, reference.artifact_id, reference.digest, reference.model_dump_json()))
        return reference

    @staticmethod
    def _read_bytes(path: Path, reference: ArtifactRef) -> bytes:
        if path.is_symlink():
            raise StoreFailure(ErrorCode.NOT_AUTHORIZED, 'Artifact cannot be a symbolic link.')
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                os.close(fd)
                raise StoreFailure(ErrorCode.NOT_AUTHORIZED, 'Artifact must be a regular file.')
            with os.fdopen(fd, 'rb') as source:
                data = source.read(reference.size_bytes + 1)
        except FileNotFoundError:
            raise StoreFailure(ErrorCode.CONFLICT, 'Committed artifact is missing.') from None
        if len(data) != reference.size_bytes or 'sha256:' + sha256(data).hexdigest() != reference.digest:
            raise StoreFailure(ErrorCode.CONFLICT, 'Artifact digest or size does not match its committed reference.')
        return data

    async def read_artifact(self, workspace_id: str, artifact_id: str) -> bytes:
        self._ensure_open()
        self._workspace(workspace_id)
        row = self._db.execute('SELECT payload FROM artifacts WHERE workspace=? AND artifact=?', (workspace_id, artifact_id)).fetchone()
        if row is None:
            raise StoreFailure(ErrorCode.NOT_AUTHORIZED, 'Artifact is unavailable in this workspace.')
        reference = ArtifactRef.model_validate_json(row['payload'])
        return self._read_bytes(self._artifact_directory(workspace_id) / reference.digest.removeprefix('sha256:'), reference)

    async def sweep_orphans(self, workspace_id: str, *, min_age_seconds: float = 3600) -> tuple[str, ...]:
        if not isinstance(min_age_seconds, (int, float)) or not math.isfinite(min_age_seconds) or min_age_seconds < 0:
            raise StoreFailure(ErrorCode.INVALID_INPUT, 'Orphan retention cannot be negative.')
        directory = self._artifact_directory(workspace_id)
        referenced = {row['digest'].removeprefix('sha256:') for row in self._db.execute('SELECT digest FROM artifacts WHERE workspace=?', (workspace_id,))}
        cutoff = time.time() - min_age_seconds
        removed = []
        for path in directory.iterdir():
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_mtime > cutoff or path.name in referenced
                    or not (re.fullmatch('[0-9a-f]{64}', path.name) or path.name.startswith('.tmp-'))):
                continue
            path.unlink()
            removed.append(path.name)
        return tuple(sorted(removed))
