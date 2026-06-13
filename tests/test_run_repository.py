"""Service layer: run-history repository roundtrip over a temp SQLite DB."""
from __future__ import annotations

from policy_to_proof.db.run_repository import RunRepository


def _record(run_id: str, decision: str = "NO-SHIP") -> dict:
    return {
        "run_id": run_id, "timestamp": 1700000000.0,
        "requirement": "make this SOC 2 ready", "target": "examples/full_demo",
        "worker": "stub", "decision": decision, "halted": False,
        "escalations": [], "findings": [{"control_id": "ENC", "status": "FAIL"}],
        "alarms": [], "risk": {"score": 42, "decision": decision},
        "metrics": {"tokens_in": 0, "tokens_out": 0, "run_seconds": 0.01},
    }


def test_save_and_get_roundtrip(tmp_path):
    db = tmp_path / "t.db"
    repo = RunRepository(db)
    repo.save_run(_record("r1"))

    got = repo.get_run("r1")
    assert got is not None
    assert got["run_id"] == "r1"
    assert got["risk"]["score"] == 42
    assert got["findings"][0]["control_id"] == "ENC"


def test_get_missing_returns_none(tmp_path):
    repo = RunRepository(tmp_path / "t.db")
    assert repo.get_run("nope") is None


def test_list_runs_most_recent_first(tmp_path):
    db = tmp_path / "t.db"
    repo = RunRepository(db)
    a = _record("a"); a["timestamp"] = 100.0
    b = _record("b", decision="SHIP"); b["timestamp"] = 200.0
    repo.save_run(a)
    repo.save_run(b)

    rows = repo.list_runs()
    assert [r["run_id"] for r in rows] == ["b", "a"]   # newest first
    assert rows[0]["decision"] == "SHIP"
    assert rows[0]["risk_score"] == 42


def test_save_is_idempotent_upsert(tmp_path):
    db = tmp_path / "t.db"
    repo = RunRepository(db)
    repo.save_run(_record("r1", decision="NO-SHIP"))
    repo.save_run(_record("r1", decision="SHIP"))   # same id, replace
    rows = repo.list_runs()
    assert len(rows) == 1
    assert rows[0]["decision"] == "SHIP"
