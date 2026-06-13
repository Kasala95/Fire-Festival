"""PILLAR 4 — OBSERVABILITY: persistence + replay.

Checkpoint results are persisted to JSON so any gate can be replayed from disk
without re-running prior stages (the SHOULD requirement). A run is one JSON file
under runs/<run_id>.json holding: inputs, per-checkpoint results, findings,
alarms, spans, metrics, and the final decision — a full audit trail for the
auditor user story.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

RUNS_DIR = Path(os.environ.get("POLICY_TO_PROOF_RUNS", "runs"))


class RunStore:
    def __init__(self, runs_dir: Path | str = RUNS_DIR) -> None:
        self.dir = Path(runs_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def path(self, run_id: str) -> Path:
        return self.dir / f"{run_id}.json"

    def save(self, run_id: str, record: dict) -> Path:
        p = self.path(run_id)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2, default=str)
        return p

    def load(self, run_id: str) -> dict:
        with open(self.path(run_id), "r", encoding="utf-8") as fh:
            return json.load(fh)

    def exists(self, run_id: str) -> bool:
        return self.path(run_id).exists()

    def checkpoint(self, run_id: str, name: str) -> dict | None:
        """Load a single persisted checkpoint result for replay-from-gate."""
        if not self.exists(run_id):
            return None
        rec = self.load(run_id)
        for cp in rec.get("checkpoints", []):
            if cp.get("name") == name:
                return cp
        return None

    def list_runs(self) -> list[str]:
        return sorted(p.stem for p in self.dir.glob("*.json"))
