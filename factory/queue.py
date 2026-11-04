"""A SQLite-fenced single render worker, shared across server processes.

Expired work is failed, never silently resumed into a partially written directory.
The operator can retry into a new render ID; previous complete artifacts survive.
"""
from contextlib import closing
from datetime import datetime, timezone
import json
import logging
import time
from uuid import uuid4

LEASE_SECONDS = 30


def audit(db, job, event, data=None):
    db.execute('INSERT INTO audit(job,event,at,data) VALUES (?,?,?,?)',
               (str(job), event, datetime.now(timezone.utc).isoformat(),
                json.dumps(data or {}, ensure_ascii=False)))


def claim(connect, read, write, owner):
    now = time.time()
    with closing(connect()) as db, db:
        db.execute('BEGIN IMMEDIATE')
        for render_id, job in db.execute(
                "SELECT id,job FROM render_queue WHERE state='RUNNING' AND lease_until < ?", (now,)).fetchall():
            current = read(db, job)
            state = 'CANCELLED' if current['state'] == 'CANCELLING' else 'FAILED'
            current['issues'] = ['Render bị gián đoạn. Có thể thử lại; bản dựng trước vẫn được giữ.']
            current.pop('pending_render_id', None)
            write(db, job, state, current)
            db.execute('UPDATE render_queue SET state=? WHERE id=?', (state, render_id))
            audit(db, job, 'render_interrupted', {'render_id': render_id})
        if db.execute("SELECT 1 FROM render_queue WHERE state='RUNNING'").fetchone():
            return None
        row = db.execute("SELECT id,job FROM render_queue WHERE state='QUEUED' ORDER BY created,id LIMIT 1").fetchone()
        if row is None:
            return None
        render_id, job = row
        db.execute("UPDATE render_queue SET state='RUNNING',owner=?,lease_until=? WHERE id=?",
                   (owner, now + LEASE_SECONDS, render_id))
        current = read(db, job)
        write(db, job, 'RENDERING', current)
        audit(db, job, 'render_started', {'render_id': render_id})
        return job, render_id


def heartbeat(connect, read, job, render_id, owner, stop):
    if stop.is_set():
        raise RuntimeError('Worker shutdown')
    with closing(connect()) as db, db:
        changed = db.execute("UPDATE render_queue SET lease_until=? WHERE id=? AND owner=? AND state='RUNNING' "
                             "AND lease_until>=?", (time.time() + LEASE_SECONDS, render_id, owner, time.time())).rowcount
        if not changed:
            raise RuntimeError('Render lease lost')
        if read(db, job)['state'] == 'CANCELLING':
            raise RuntimeError('Render cancelled')


def work(connect, read, write, execute, stop):
    owner = str(uuid4())
    while not stop.is_set():
        try:
            item = claim(connect, read, write, owner)
            if item:
                execute(*item, owner, stop)
                continue
        except Exception:
            logging.getLogger(__name__).exception('Render worker iteration failed')
        stop.wait(.5)
