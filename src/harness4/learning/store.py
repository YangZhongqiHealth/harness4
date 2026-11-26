"""Private local release authority, immutable evidence and transactional pointers.

Local OS owner is trusted. Model proposers receive JSON values, not this object.
This is not isolation against arbitrary Python with the same user's privileges.
"""
from contextlib import contextmanager
import json
import os
import sqlite3
import time
from uuid import uuid4

from ..adapters.sqlite_state import SQLiteState, _private_file
from ..contracts import PolicyBundle, digest, text_digest
from .contracts import Profile, Episode, Feedback, Dataset, baseline, label_keys


def encode(value):
    if hasattr(value, 'model_dump'):
        value = value.model_dump(mode='json')
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


class LearningError(ValueError):
    pass


class LearningStore:
    def __init__(self, directory):
        self.lock = SQLiteState(directory)
        self.db = None
        try:
            path = self.lock.root / 'learning.sqlite3'
            os.close(_private_file(path))
            for suffix in ('-wal', '-shm', '-journal'):
                sidecar = path.with_name(path.name + suffix)
                if sidecar.exists() or sidecar.is_symlink():
                    os.close(_private_file(sidecar))
            self.db = sqlite3.connect(path, isolation_level=None, timeout=1)
            self.db.row_factory = sqlite3.Row
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('PRAGMA synchronous=FULL')
            with self.transaction():
                version = self.db.execute('PRAGMA user_version').fetchone()[0]
                if version not in (0, 1):
                    raise LearningError('Unsupported learning schema.')
                if not version:
                    self.db.execute('CREATE TABLE objects (id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL)')
                    self.db.execute('CREATE TABLE config (id INTEGER PRIMARY KEY CHECK(id=1), repository TEXT, mode TEXT, profile TEXT, baseline TEXT, active TEXT, generation INTEGER, epoch INTEGER)')
                    self.db.execute('CREATE TABLE audit (seq INTEGER PRIMARY KEY, kind TEXT, payload TEXT)')
                    self.db.execute('CREATE TABLE retractions (feedback TEXT PRIMARY KEY, reason TEXT)')
                    self.db.execute('CREATE TABLE revoked (policy TEXT PRIMARY KEY)')
                    self.db.execute('CREATE TABLE partitions (identity TEXT PRIMARY KEY, split TEXT)')
                    self.db.execute('CREATE TABLE consumed (identity TEXT PRIMARY KEY, cycle TEXT)')
                    self.db.execute('CREATE TABLE cycles (id TEXT PRIMARY KEY, payload TEXT, status TEXT, report TEXT)')
                    self.db.execute('CREATE TABLE approvals (id TEXT PRIMARY KEY, report TEXT, generation INTEGER, epoch INTEGER, expires REAL, used INTEGER, operator TEXT)')
                    self.db.execute('CREATE TABLE activations (policy TEXT PRIMARY KEY)')
                    self.db.execute('PRAGMA user_version=1')
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None
        self.lock.close()

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def put(self, kind, value):
        payload = encode(value)
        key = text_digest(payload)
        prior = self.db.execute('SELECT kind,payload FROM objects WHERE id=?', (key,)).fetchone()
        if prior and (prior['kind'], prior['payload']) != (kind, payload):
            raise LearningError('Object type/hash collision.')
        self.db.execute('INSERT OR IGNORE INTO objects VALUES(?,?,?)', (key, kind, payload))
        return key

    def get(self, key, kind):
        row = self.db.execute('SELECT * FROM objects WHERE id=?', (key,)).fetchone()
        if row is None or row['kind'] != kind or text_digest(row['payload']) != key:
            raise LearningError('Missing, corrupt or wrong-kind learning record.')
        return json.loads(row['payload'])

    def audit(self, kind, payload):
        self.db.execute('INSERT INTO audit(kind,payload) VALUES(?,?)', (kind, encode(payload)))

    def config(self):
        row = self.db.execute('SELECT * FROM config WHERE id=1').fetchone()
        if row is None:
            raise LearningError('Initialize learning before use.')
        return dict(row)

    def initialize(self, repository, profile: Profile, *, mode='production'):
        if mode not in ('production', 'demo') or '/' not in repository:
            raise LearningError('Invalid learning scope.')
        if self.db.execute('SELECT 1 FROM config').fetchone():
            raise LearningError('Learning scope is already initialized.')
        policy = baseline(repository, profile)
        with self.transaction():
            profile_id = self.put('profile', profile)
            policy_id = self.put('policy', policy)
            self.db.execute('INSERT INTO config VALUES(1,?,?,?,?,?,0,0)',
                            (repository, mode, profile_id, policy_id, policy_id))
            self.db.execute('INSERT INTO activations VALUES(?)', (policy_id,))
            self.audit('initialized', {'repository': repository, 'mode': mode, 'policy': policy_id})
        return self.config()

    def profile(self):
        return Profile.model_validate_json(encode(self.get(self.config()['profile'], 'profile')))

    def policy(self, key=None):
        key = key or self.config()['active']
        if self.db.execute('SELECT 1 FROM revoked WHERE policy=?', (key,)).fetchone():
            raise LearningError('Policy revoked; stop this run.')
        policy = PolicyBundle.model_validate_json(encode(self.get(key, 'policy')))
        config = self.config()
        if policy.scope.workspace_id != config['repository'] or policy.model_profile != config['profile']:
            raise LearningError('Policy is incompatible with scope/model.')
        return policy

    def record_episode(self, episode: Episode):
        c = self.config()
        if (episode.repository != c['repository'] or episode.profile_hash != c['profile'] or
                (c['mode'] == 'production' and episode.evidence_class != 'live')):
            raise LearningError('Episode scope, profile or evidence class mismatch.')
        self.policy(episode.policy_hash)
        return self.put('episode', episode)

    def feedback(self, item: Feedback):
        episode = Episode.model_validate_json(encode(self.get(item.episode_id, 'episode')))
        if self.config()['mode'] == 'production' and item.source == 'scripted_demo':
            raise LearningError('Scripted feedback cannot enter production.')
        contents = json.loads(episode.input.contents_json)
        if len(label_keys(item.labels)) != len(item.labels) or any(
                x.path not in contents or x.line > max(1, len(contents[x.path].splitlines())) for x in item.labels):
            raise LearningError('Invalid or duplicate feedback finding location.')
        # A correction must explicitly retract the old label before replacement.
        for row in self.db.execute("SELECT id,payload FROM objects WHERE kind='feedback'"):
            old = json.loads(row['payload'])
            if old['episode_id'] == item.episode_id and row['id'] != digest(item) and not self.is_retracted(row['id']):
                raise LearningError('Conflicting feedback; retract the previous record first.')
        with self.transaction():
            key = self.put('feedback', item)
            if self.is_retracted(key):
                raise LearningError('Retracted feedback cannot be reused.')
            self.audit('feedback', {'id': key, 'operator': item.operator})
        return key

    def is_retracted(self, key):
        return self.db.execute('SELECT 1 FROM retractions WHERE feedback=?', (key,)).fetchone() is not None

    def cases(self, dataset_id):
        dataset = Dataset.model_validate_json(encode(self.get(dataset_id, 'dataset')))
        result = []
        for member in dataset.cases:
            if self.is_retracted(member.feedback_id):
                raise LearningError('Dataset depends on retracted feedback.')
            feedback = Feedback.model_validate_json(encode(self.get(member.feedback_id, 'feedback')))
            episode = Episode.model_validate_json(encode(self.get(feedback.episode_id, 'episode')))
            result.append((member, feedback, episode))
        return result

    def dataset(self, dataset: Dataset):
        groups, inputs, ids, splits = {}, {}, set(), set()
        identities = []
        for member in dataset.cases:
            if member.feedback_id in ids or self.is_retracted(member.feedback_id):
                raise LearningError('Duplicate or retracted evidence.')
            ids.add(member.feedback_id)
            feedback = Feedback.model_validate_json(encode(self.get(member.feedback_id, 'feedback')))
            episode = Episode.model_validate_json(encode(self.get(feedback.episode_id, 'episode')))
            fingerprint = digest(episode.input)
            if fingerprint in inputs:
                raise LearningError('Duplicate source input, even with different IDs.')
            inputs[fingerprint] = member.split
            if feedback.group in groups and groups[feedback.group] != member.split:
                raise LearningError('A source group crosses data splits.')
            groups[feedback.group] = member.split
            splits.add(member.split)
            identities.extend((('group:' + feedback.group, member.split), ('input:' + fingerprint, member.split)))
        if splits != {'dev', 'target', 'anchor'}:
            raise LearningError('Development, target and retention anchors are all required.')
        with self.transaction():
            for identity, split in identities:
                prior = self.db.execute('SELECT split FROM partitions WHERE identity=?', (identity,)).fetchone()
                if prior and prior['split'] != split:
                    raise LearningError('Previously exposed data cannot move between splits.')
                self.db.execute('INSERT OR IGNORE INTO partitions VALUES(?,?)', (identity, split))
            key = self.put('dataset', dataset)
            self.audit('dataset', {'id': key, 'cases': len(ids)})
        return key

    def consume(self, dataset_id, cycle):
        identities = set()
        for member, feedback, episode in self.cases(dataset_id):
            if member.split != 'dev':
                identities.update(('group:' + feedback.group, 'input:' + digest(episode.input)))
        with self.transaction():
            for identity in sorted(identities):
                if self.db.execute('SELECT 1 FROM consumed WHERE identity=?', (identity,)).fetchone():
                    raise LearningError('Release cohort already consumed; supply fresh independent groups.')
                self.db.execute('INSERT INTO consumed VALUES(?,?)', (identity, cycle))
            self.audit('sealed.cohort_consumed', {'cycle': cycle, 'dataset': dataset_id})

    def report(self, report_id):
        report = self.get(report_id, 'report')
        row = self.db.execute('SELECT status,report FROM cycles WHERE id=?', (report['cycle'],)).fetchone()
        if not row or row['status'] != 'complete' or row['report'] != report_id:
            raise LearningError('Report lacks a completed trusted evaluator receipt.')
        return report

    def eligible_report(self, report_id):
        report = self.report(report_id)
        c = self.config()
        self.cases(report['dataset'])
        if (report['decision'] != 'eligible' or report['scope'] != c['mode'] or
                report['profile'] != c['profile'] or report['incumbent'] != c['active'] or
                report['generation'] != c['generation'] or report['epoch'] != c['epoch'] or
                report['expires'] <= time.time()):
            raise LearningError('Report is ineligible, stale, expired or incompatible.')
        self.policy(report['candidate'])
        return report

    def approve(self, report_id, operator):
        if not operator.strip():
            raise LearningError('Operator identity required.')
        with self.transaction():
            report = self.eligible_report(report_id)
            approval = str(uuid4())
            self.db.execute('INSERT INTO approvals VALUES(?,?,?,?,?,0,?)',
                            (approval, report_id, report['generation'], report['epoch'], report['expires'], operator))
            self.audit('approved', {'approval': approval, 'report': report_id, 'operator': operator})
        return approval

    def promote(self, approval):
        with self.transaction():
            row = self.db.execute('SELECT * FROM approvals WHERE id=?', (approval,)).fetchone()
            if row is None or row['used'] or row['expires'] <= time.time():
                raise LearningError('Unknown, expired or already used approval.')
            report = self.eligible_report(row['report'])
            c = self.config()
            if (row['generation'], row['epoch']) != (c['generation'], c['epoch']):
                raise LearningError('Approval is stale.')
            self.db.execute('UPDATE config SET active=?,generation=generation+1 WHERE id=1 AND generation=?',
                            (report['candidate'], c['generation']))
            self.db.execute('UPDATE approvals SET used=1 WHERE id=?', (approval,))
            self.db.execute('INSERT OR IGNORE INTO activations VALUES(?)', (report['candidate'],))
            self.audit('promoted', {'from': c['active'], 'to': report['candidate'], 'report': row['report'],
                                   'operator': row['operator'], 'generation': c['generation'] + 1})
        return self.config()

    def rollback(self, target, *, expected_generation, operator, reason):
        if not operator.strip() or not reason.strip():
            raise LearningError('Rollback requires operator and reason.')
        with self.transaction():
            c = self.config()
            if c['generation'] != expected_generation or c['active'] == target:
                raise LearningError('Stale generation or no-op rollback.')
            if not self.db.execute('SELECT 1 FROM activations WHERE policy=?', (target,)).fetchone():
                raise LearningError('Rollback target was never active.')
            self.policy(target)
            self.db.execute('UPDATE config SET active=?,generation=generation+1 WHERE id=1', (target,))
            self.audit('rolled_back', {'from': c['active'], 'to': target, 'operator': operator, 'reason': reason})
        return self.config()

    def retract(self, feedback_id, *, operator, reason):
        self.get(feedback_id, 'feedback')
        if not operator.strip() or not reason.strip():
            raise LearningError('Retraction requires operator and reason.')
        with self.transaction():
            self.db.execute('INSERT OR IGNORE INTO retractions VALUES(?,?)', (feedback_id, reason))
            invalid = set()
            for row in self.db.execute("SELECT id,payload FROM objects WHERE kind='dataset'"):
                if any(c['feedback_id'] == feedback_id for c in json.loads(row['payload'])['cases']):
                    invalid.add(row['id'])
            revoked = set()
            # Propagate through candidate ancestry, not only direct report dependencies.
            candidates = [json.loads(r['payload']) for r in self.db.execute("SELECT payload FROM objects WHERE kind='candidate'")]
            changed = True
            while changed:
                before = len(revoked)
                revoked.update(x['policy'] for x in candidates if x['dataset'] in invalid or x['parent'] in revoked)
                changed = len(revoked) != before
            for key in revoked:
                self.db.execute('INSERT OR IGNORE INTO revoked VALUES(?)', (key,))
            c = self.config()
            target = c['baseline'] if c['active'] in revoked else c['active']
            self.db.execute('UPDATE config SET epoch=epoch+1,active=?,generation=generation+1 WHERE id=1', (target,))
            self.audit('evidence.retracted', {'feedback': feedback_id, 'operator': operator, 'reason': reason,
                                             'revoked': sorted(revoked), 'active': target})
        return self.config()

    def status(self):
        c = self.config()
        return {**c, 'cycles': [dict(r) for r in self.db.execute('SELECT id,status,report FROM cycles')],
                'audit': [{'seq': r['seq'], 'kind': r['kind'], **json.loads(r['payload'])}
                          for r in self.db.execute('SELECT * FROM audit ORDER BY seq')]}
