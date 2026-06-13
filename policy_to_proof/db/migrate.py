"""SQLite connection + idempotent migration for run history.

Run directly to (re)apply the schema:

    python -m policy_to_proof.db.migrate

``migrate()`` is safe to call on every connection — the schema uses
``CREATE TABLE IF NOT EXISTS`` so it is a no-op once applied.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("POLICY_TO_PROOF_DB", "runs/policy_to_proof.db"))
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection with dict-like rows. Creates parent dir."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Apply the schema. Idempotent."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def get_db(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Connect and ensure the schema exists. The one-call entry point."""
    conn = connect(db_path)
    migrate(conn)
    return conn


if __name__ == "__main__":
    with get_db() as c:
        tables = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
    print(f"migrated {DB_PATH} — tables: {', '.join(tables)}")
