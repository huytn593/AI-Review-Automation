"""Environment diagnostics and versioned SQLite initialization."""
import platform
import shutil
import sqlite3


def migrate(db: sqlite3.Connection) -> None:
    with db:
        db.execute("BEGIN IMMEDIATE")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version > 1:
            raise RuntimeError("Database schema is newer than this application")
        if version == 0:
            db.execute(
                "CREATE TABLE IF NOT EXISTS jobs "
                "(id TEXT PRIMARY KEY, key TEXT UNIQUE, state TEXT, data TEXT)"
            )
            db.execute("PRAGMA user_version=1")


def diagnostics() -> dict:
    return {
        "python": platform.python_version(),
        "os": platform.system(),
        "tools_on_path": {
            tool: shutil.which(tool) is not None
            for tool in ("ffmpeg", "ffprobe", "nvidia-smi", "ollama")
        },
    }
