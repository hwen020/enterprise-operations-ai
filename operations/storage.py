"""Checksummed, transactional SQLite migrations."""
import hashlib
from pathlib import Path
import sqlite3
ROOT = Path(__file__).resolve().parents[1]
def connect(path):
    db = sqlite3.connect(str(path), timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=15000")
    return db
def migrate(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = connect(path)
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE IF NOT EXISTS migrations(version TEXT PRIMARY KEY,digest TEXT NOT NULL)")
        for file in sorted((ROOT/"migrations").glob("*.sql")):
            value = file.read_text(encoding="utf-8")
            digest = hashlib.sha256(value.encode()).hexdigest()
            old = db.execute("SELECT digest FROM migrations WHERE version=?", (file.stem,)).fetchone()
            if old:
                if old[0] != digest: raise RuntimeError("Migration checksum mismatch")
                continue
            buffer = ""
            for line in value.splitlines(True):
                buffer += line
                if sqlite3.complete_statement(buffer):
                    db.execute(buffer)
                    buffer = ""
            if buffer.strip(): raise RuntimeError("Incomplete migration")
            db.execute("INSERT INTO migrations VALUES(?,?)", (file.stem,digest))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally: db.close()
