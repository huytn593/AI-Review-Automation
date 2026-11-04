"""Environment diagnostics and versioned SQLite initialization."""
import platform
import shutil
import sqlite3
import json
from datetime import datetime, timezone


def migrate(db: sqlite3.Connection) -> None:
    with db:
        db.execute("BEGIN IMMEDIATE")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version > 3:
            raise RuntimeError("Database schema is newer than this application")
        if version == 0:
            db.execute(
                "CREATE TABLE IF NOT EXISTS jobs "
                "(id TEXT PRIMARY KEY, key TEXT UNIQUE, state TEXT, data TEXT)"
            )
            db.execute("PRAGMA user_version=1")
        if version < 2:
            db.execute("CREATE TABLE IF NOT EXISTS render_queue (id TEXT PRIMARY KEY, job TEXT NOT NULL, "
                       "state TEXT NOT NULL, owner TEXT, lease_until REAL, created REAL NOT NULL)")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_pending_render ON render_queue(job) "
                       "WHERE state IN ('QUEUED','RUNNING')")
            db.execute("CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, job TEXT NOT NULL, "
                       "event TEXT NOT NULL, at TEXT NOT NULL, data TEXT NOT NULL)")
            for job, state, payload in db.execute("SELECT id,state,data FROM jobs WHERE state IN ('RENDERING','CANCELLING')").fetchall():
                data = json.loads(payload)
                data['issues'] = ['Render cũ bị gián đoạn trước khi nâng cấp. Hãy kiểm tra và thử lại.']
                db.execute('UPDATE jobs SET state=?,data=? WHERE id=?',
                           ('CANCELLED' if state == 'CANCELLING' else 'FAILED', json.dumps(data), job))
                db.execute('INSERT INTO audit(job,event,at,data) VALUES (?,?,?,?)',
                           (job, 'legacy_render_recovered', datetime.now(timezone.utc).isoformat(), '{}'))
            for job, payload in db.execute("SELECT id,data FROM jobs WHERE state IN ('APPROVED','AWAITING_APPROVAL')").fetchall():
                data = json.loads(payload)
                previous = data.pop('approval', None)
                data['issues'] = ['Bản dựng cũ chưa có checksum ràng buộc. Cần dựng và duyệt lại.']
                db.execute("UPDATE jobs SET state='QC_FAILED',data=? WHERE id=?", (json.dumps(data), job))
                db.execute('INSERT INTO audit(job,event,at,data) VALUES (?,?,?,?)',
                           (job, 'legacy_approval_invalidated', datetime.now(timezone.utc).isoformat(),
                            json.dumps({'previous_approval': previous})))
            db.execute("PRAGMA user_version=2")
        if version < 3:
            db.execute('CREATE TABLE IF NOT EXISTS media_assets (id TEXT PRIMARY KEY, job TEXT NOT NULL, '
                       'sha256 TEXT NOT NULL, data TEXT NOT NULL, UNIQUE(job,sha256))')
            db.execute('PRAGMA user_version=3')


def diagnostics() -> dict:
    return {
        "python": platform.python_version(),
        "os": platform.system(),
        "tools_on_path": {
            tool: shutil.which(tool) is not None
            for tool in ("ffmpeg", "ffprobe", "nvidia-smi", "ollama")
        },
    }
