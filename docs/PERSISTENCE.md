# Local durable state repository

`harness4.adapters.sqlite_state.SQLiteState` implements the async `StatePort` load
and commit interface plus trusted admission, local run ownership, event replay,
operation receipts, task results and private artifacts. It uses stdlib SQLite WAL,
foreign keys, FULL synchronization, transactional schema migration and a versioned
canonicalizer marker. There are no provider or tool calls inside transactions.

Run the credential-free persistence example after installing the package:

```sh
python examples/durable_task.py
```

The example admits a demo task, commits transitions and an artifact-backed result,
closes the repository and reads the same result after restart. It creates and
removes its own temporary directory. The ship CLI is not yet a durable orchestrator;
this repository is the foundation for admission and execution in H4-004 onward.

## Consistency and recovery

- An OS lock permits one coordinator per state directory. Same-process second
  instances are refused as well. Use a local filesystem; distributed deployment,
  network filesystem lock guarantees and timed worker leases are outside P0.
- Workspace + request key is unique. Matching retries return the existing task and
  original policy pin even if the active policy changed. Different input conflicts.
  The caller must resolve grants and policy before trusted `admit`; this method is
  not an external authorization endpoint.
- Acquiring a run increments its fence. Commits require both live local ownership
  and the expected state version. Restart obtains a new coordinator owner and can
  acquire a new run; prior runs cannot commit. Pending intents remain visible.
- State transition, event batch, step snapshot, effect intents and an optional final
  TaskResult commit atomically. Event sequence is contiguous per task; duplicate IDs,
  cross-workspace events and conflicting intents roll back the entire transaction.
- Receipts are persisted before reduction. Repeating the identical receipt is safe;
  replacing one conflicts. Operation identity stays stable across retries. The store
  does not execute or retry effects, nor infer success from an intent.
- A task with a pending operation cannot transition directly to a successful/failed/
  cancelled terminal state. It must reconcile; unresolved uncertainty may terminate
  as UNKNOWN_EFFECT. Audited reconciliation of terminal states is future work.
- Results must match the terminal state, task, session and policy pin. Artifact refs
  must already exist in the same workspace, and action receipts must match committed
  operations belonging to the task. The application/kernel is responsible
  for producing results when required and verifying model/profile/outcome semantics.

Use `events(workspace, task, after_seq)` to replay committed events without re-running
inference. `steps` returns immutable ordered state snapshots. `pending_operations`
provides the recovery worklist; consumers must reconcile it before new dispatch.

## Artifacts and privacy

The state root must be a private directory (0700 on POSIX); files are created 0600.
The supplied root is operator configuration, not an untrusted task path. All public
repository lookups take workspace explicitly. Workspace IDs are hashed into internal
artifact directories; callers cannot use a filename to escape the directory.

Artifacts are written to a temporary file, fsynced, atomically renamed to a content
hash and only then referenced in a database transaction. Reads verify the committed
size and SHA-256. Symlink paths and nonregular files are rejected. File creation can
succeed before a failed DB transaction: `sweep_orphans(workspace, min_age_seconds=...)`
removes only aged generated files without references, leaving referenced shared bytes
and unrelated files intact. Default grace period is one hour. Cleanup is explicitly
invoked, never automatic on an arbitrary directory.

This is a consistency boundary, not protection from another process with the same
OS credentials that can edit the database. Untrusted execution needs a separate
sandbox/credential boundary. These tables do not store raw provider bodies by design,
but task inputs/results may contain user data: the caller owns redaction and retention.
Backup/restore tooling, encryption at rest, remote stores, distributed worker leases,
and the complete agent/policy/learning schema remain separate work.
