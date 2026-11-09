"""Transactional job queue, leases, checkpoints and evidence. No in-memory authority."""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time
import uuid

ROOT = Path(__file__).resolve().parent
TERMINAL = {'completed', 'failed', 'blocked', 'cancelled'}


class Conflict(ValueError):
    pass


class JobStore:
    def __init__(self, path=ROOT / 'data/jobs.sqlite3'):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, query TEXT NOT NULL, status TEXT NOT NULL,
                    created REAL NOT NULL, updated REAL NOT NULL, run_at REAL NOT NULL,
                    started REAL, owner TEXT, lease REAL, attempts INTEGER NOT NULL DEFAULT 0,
                    max_steps INTEGER NOT NULL, steps INTEGER NOT NULL DEFAULT 0,
                    checkpoint TEXT NOT NULL DEFAULT '{}', result TEXT NOT NULL DEFAULT '{}',
                    error TEXT, idempotency_key TEXT UNIQUE, fingerprint TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(status, run_at, lease);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
                    at REAL NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS job_events ON events(job_id, id);
                CREATE TABLE IF NOT EXISTS lessons (
                    digest TEXT PRIMARY KEY, job_id TEXT NOT NULL, lesson TEXT NOT NULL, at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS workers (id TEXT PRIMARY KEY, heartbeat REAL NOT NULL);
            ''')
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def decode(row):
        if row is None:
            return None
        value = dict(row)
        for key in ('checkpoint', 'result'):
            value[key] = json.loads(value[key])
        return value

    def submit(self, query, *, max_steps=24, run_at=None, idempotency_key=None, initial_state=None):
        if not isinstance(query, str) or not 3 <= len(query.strip()) <= 12000:
            raise ValueError('query must contain 3 to 12000 characters')
        if type(max_steps) is not int or not 2 <= max_steps <= 80:
            raise ValueError('max_steps must be an integer from 2 to 80')
        if run_at is not None and (type(run_at) not in (int, float) or not math.isfinite(run_at) or run_at < 0):
            raise ValueError('run_at must be a finite Unix timestamp')
        if idempotency_key is not None and (not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128):
            raise ValueError('invalid idempotency key')
        query = query.strip()
        identity = [query, max_steps, run_at]
        if initial_state is not None:
            if not isinstance(initial_state, dict):
                raise ValueError('initial state must be an object')
            identity.append(initial_state)
        fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        now, ident = time.time(), uuid.uuid4().hex
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if idempotency_key:
                old = db.execute('SELECT * FROM jobs WHERE idempotency_key=?', (idempotency_key,)).fetchone()
                if old:
                    if old['fingerprint'] != fingerprint:
                        raise Conflict('idempotency key already used with a different request')
                    return self.decode(old)
            db.execute('INSERT INTO jobs (id,query,status,created,updated,run_at,max_steps,idempotency_key,fingerprint,checkpoint) VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (ident, query, 'queued', now, now, now if run_at is None else run_at, max_steps, idempotency_key, fingerprint, json.dumps(initial_state or {})))
            self._event(db, ident, 'queued', {'run_at': now if run_at is None else run_at})
        return self.get(ident)

    def get(self, ident):
        with self.connect() as db:
            return self.decode(db.execute('SELECT * FROM jobs WHERE id=?', (ident,)).fetchone())

    def list(self, limit=100):
        with self.connect() as db:
            return [self.decode(r) for r in db.execute('SELECT * FROM jobs ORDER BY created DESC LIMIT ?', (min(100, limit),))]

    def events(self, ident, after=0):
        with self.connect() as db:
            return [{**dict(row), 'detail': json.loads(row['detail'])} for row in db.execute(
                'SELECT * FROM events WHERE job_id=? AND id>? ORDER BY id LIMIT 500', (ident, after))]

    @staticmethod
    def _event(db, ident, kind, detail):
        db.execute('INSERT INTO events(job_id,at,kind,detail) VALUES(?,?,?,?)',
                   (ident, time.time(), kind, json.dumps(detail)))

    def claim(self, owner, lease_seconds=30):
        now = time.time()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM jobs WHERE (status='queued' AND run_at<=?) OR (status='running' AND lease<?) ORDER BY run_at LIMIT 1", (now, now)).fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET status='running',owner=?,lease=?,attempts=attempts+1,started=COALESCE(started,?),updated=? WHERE id=?", (owner, now + lease_seconds, now, now, row['id']))
            self._event(db, row['id'], 'recovered' if row['status'] == 'running' else 'started', {})
            return self.decode(db.execute('SELECT * FROM jobs WHERE id=?', (row['id'],)).fetchone())

    def heartbeat(self, ident, owner):
        with self.connect() as db:
            return bool(db.execute("UPDATE jobs SET lease=?,updated=? WHERE id=? AND owner=? AND status='running'", (time.time()+30, time.time(), ident, owner)).rowcount)

    def checkpoint(self, ident, owner, state, steps, kind='step', detail=None):
        with self.connect() as db:
            changed = db.execute("UPDATE jobs SET checkpoint=?,steps=?,updated=? WHERE id=? AND owner=? AND status='running'", (json.dumps(state), steps, time.time(), ident, owner)).rowcount
            if not changed:
                raise Conflict('job lease lost or job cancelled')
            self._event(db, ident, kind, detail or {})

    def finish(self, ident, owner, status, result=None, error=None):
        if status not in TERMINAL:
            raise ValueError('invalid final state')
        with self.connect() as db:
            changed = db.execute("UPDATE jobs SET status=?,result=?,error=?,owner=NULL,lease=NULL,updated=? WHERE id=? AND owner=? AND status='running'", (status, json.dumps(result or {}), error, time.time(), ident, owner)).rowcount
            if changed:
                self._event(db, ident, status, {'error': error} if error else {})
            return bool(changed)

    def defer(self, ident, owner, state, steps, delay):
        """Persist a bounded provider wait without replaying successful actions."""
        if type(delay) not in (int, float) or not math.isfinite(delay) or not 1 <= delay <= 3600:
            raise ValueError('invalid provider cooldown')
        now = time.time()
        with self.connect() as db:
            changed = db.execute("UPDATE jobs SET status='queued',run_at=?,updated=?,checkpoint=?,steps=?,owner=NULL,lease=NULL,error=NULL WHERE id=? AND owner=? AND status='running'",
                                 (now + delay, now, json.dumps(state), steps, ident, owner)).rowcount
            if not changed:
                raise Conflict('job lease lost or job cancelled')
            self._event(db, ident, 'provider_wait', {'retry_at': now + delay, 'delay_seconds': delay})
        return self.get(ident)

    def cancel(self, ident):
        with self.connect() as db:
            changed = db.execute("UPDATE jobs SET status='cancelled',updated=?,lease=NULL WHERE id=? AND status IN ('running','queued')", (time.time(), ident)).rowcount
            if changed:
                self._event(db, ident, 'cancelled', {})
        return self.get(ident)

    def retry(self, ident):
        with self.connect() as db:
            changed = db.execute("UPDATE jobs SET status='queued',run_at=?,started=NULL,updated=?,error=NULL,owner=NULL,lease=NULL,steps=0 WHERE id=? AND status IN ('blocked','failed','cancelled')", (time.time(), time.time(), ident)).rowcount
            if not changed:
                raise Conflict('only blocked, failed or cancelled jobs can be retried')
            self._event(db, ident, 'retry', {})
        return self.get(ident)

    def release(self, ident, owner):
        with self.connect() as db:
            db.execute("UPDATE jobs SET lease=0 WHERE id=? AND owner=? AND status='running'", (ident, owner))

    def remember(self, ident, lesson):
        if not isinstance(lesson, str) or not lesson.strip():
            return
        from execution_learning import public_text
        lesson = public_text(lesson)
        if not lesson:
            return
        with self.connect() as db:
            row = db.execute('SELECT status FROM jobs WHERE id=?', (ident,)).fetchone()
            if not row or row['status'] != 'completed':
                raise ValueError('only verified completed jobs can contribute lessons')
            db.execute('INSERT OR REPLACE INTO lessons VALUES(?,?,?,?)', (hashlib.sha256(lesson.encode()).hexdigest(), ident, lesson, time.time()))
            db.execute('DELETE FROM lessons WHERE digest NOT IN (SELECT digest FROM lessons ORDER BY at DESC LIMIT 200)')

    def lessons(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT job_id,lesson FROM lessons ORDER BY at DESC LIMIT 8')]

    def lesson_records(self):
        with self.connect() as db:
            rows = db.execute("SELECT l.digest,l.job_id,l.lesson,l.at,j.result FROM lessons l JOIN jobs j ON j.id=l.job_id WHERE j.status='completed' ORDER BY l.at DESC LIMIT 200")
            records = []
            for row in rows:
                result = json.loads(row['result'])
                records.append({'id': row['digest'], 'job_id': row['job_id'], 'lesson': row['lesson'],
                    'created': row['at'], 'checks_passed': sum(c.get('exit_code') == 0 for c in result.get('checks', [])),
                    'accepted': result.get('review', {}).get('accepted') is True,
                    'files': [{'path': f['path'], 'sha256': f['sha256']} for f in result.get('files', [])]})
            return records

    def forget_lesson(self, digest):
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError('invalid lesson identifier')
        with self.connect() as db:
            return bool(db.execute('DELETE FROM lessons WHERE digest=?', (digest,)).rowcount)

    def worker_ping(self, owner):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO workers VALUES(?,?)', (owner, time.time()))
            db.execute('DELETE FROM workers WHERE heartbeat<?', (time.time()-60,))

    def worker_count(self):
        with self.connect() as db:
            return db.execute('SELECT COUNT(*) FROM workers WHERE heartbeat>?', (time.time()-15,)).fetchone()[0]
