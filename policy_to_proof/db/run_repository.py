"""Run-history repository — the service layer over the SQLite store.

Thin data-access object: turns a finished run *record* (the same dict persisted
to runs/<id>.json) into a row, and reads rows back for the history dashboard.
The JSON file remains the source of truth; this is a queryable index on top, so
``save_run`` is best-effort from the harness's point of view.
"""
from __future__ import annotations

import json
from pathlib import Path

from .migrate import DB_PATH, get_db


class RunRepository:
    def __init__(self, db_path: Path | str = DB_PATH) -> None:
        self._db_path = db_path

    def save_run(self, record: dict) -> None:
        """Insert (or replace) one run from its full record dict."""
        risk = record.get("risk") or {}
        row = (
            record["run_id"],
            float(record.get("timestamp", 0.0)),
            record.get("requirement"),
            record.get("target"),
            record.get("worker"),
            record.get("decision"),
            risk.get("score"),
            1 if record.get("halted") else 0,
            1 if record.get("escalations") else 0,
            json.dumps(record, default=str),
        )
        conn = get_db(self._db_path)
        try:
            with conn:
                conn.execute(
                    """INSERT OR REPLACE INTO runs
                       (run_id, created_at, requirement, target, worker,
                        decision, risk_score, halted, escalated, record_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    row,
                )
        finally:
            conn.close()

    def list_runs(self, limit: int = 50) -> list[dict]:
        """Most-recent-first summary rows for the history table."""
        conn = get_db(self._db_path)
        try:
            cur = conn.execute(
                """SELECT run_id, created_at, requirement, target, worker,
                          decision, risk_score, halted, escalated
                   FROM runs ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_run(self, run_id: str) -> dict | None:
        """Full persisted record for one run, or None if unknown."""
        conn = get_db(self._db_path)
        try:
            cur = conn.execute(
                "SELECT record_json FROM runs WHERE run_id = ?", (run_id,))
            row = cur.fetchone()
            return json.loads(row["record_json"]) if row else None
        finally:
            conn.close()
