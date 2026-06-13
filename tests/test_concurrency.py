"""Concurrency stress: parallel full scans must all complete with a consistent DB."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from policy_to_proof.db.run_repository import RunRepository
from policy_to_proof.loop.orchestrator import Harness
from policy_to_proof.worker import get_worker

FULL = "policy_to_proof/examples/full_demo"
HALT = "policy_to_proof/examples/halt_demo"
N = 40


def test_parallel_scans_all_complete_and_persist(tmp_path):
    db = tmp_path / "policy_to_proof.db"             # where the harness writes it

    def _scan(i):
        # share the runs dir + DB across threads (WAL must keep writes consistent)
        h = Harness(worker=get_worker("stub"), runs_dir=tmp_path)
        target = FULL if i % 2 == 0 else HALT
        rec = h.run(target, "make this SOC 2 ready", run_id=f"par-{i}")
        return rec["decision"]

    with ThreadPoolExecutor(max_workers=16) as ex:
        decisions = list(ex.map(_scan, range(N)))

    assert len(decisions) == N
    assert all(d == "NO-SHIP" for d in decisions)     # both demos are NO-SHIP
    # every run persisted exactly once, no lost/locked writes
    rows = RunRepository(db).list_runs(limit=200)
    assert len({r["run_id"] for r in rows}) == N
