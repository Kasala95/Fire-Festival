"""PR1 hardening: input caps, fail-closed scanners, worker-error handling, WAL writes."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from policy_to_proof.db.run_repository import RunRepository
from policy_to_proof.loop.orchestrator import Harness
from policy_to_proof.tools import ingest
from policy_to_proof.tools.ingest import InputRejected, ingest_text
from policy_to_proof.tools.registry import (SCANNER_ERROR_NOTE, _REGISTRY,
                                            register, run_scanner)
from policy_to_proof.types import Control
from policy_to_proof.worker import get_worker

FULL = "policy_to_proof/examples/full_demo"


# ---- input caps -----------------------------------------------------------
def test_oversize_input_rejected():
    big = "# pad\n" + ("x" * (ingest.MAX_INPUT_BYTES + 1))
    with pytest.raises(InputRejected) as ei:
        ingest_text("big.tf", big)
    assert ei.value.reason == "input_too_large"


def test_too_many_resources_rejected():
    blocks = "\n".join(f'resource "aws_x" "n{i}" {{}}'
                       for i in range(ingest.MAX_RESOURCES + 5))
    with pytest.raises(InputRejected) as ei:
        ingest_text("many.tf", blocks)
    assert ei.value.reason == "too_many_resources"


def test_run_on_oversize_file_alarms_not_crashes(tmp_path):
    big = tmp_path / "big.tf"
    big.write_text("x" * (ingest.MAX_INPUT_BYTES + 10))
    rec = Harness(worker=get_worker("stub"), runs_dir=tmp_path).run(
        str(big), "make this SOC 2 ready", "oversize")
    assert rec["errored"] is True
    assert rec["halted"] is True
    assert any(a["type"] == "INPUT_REJECTED" for a in rec["alarms"])
    assert rec["decision"] == "NO-SHIP"


def test_ingest_text_parses_like_a_file():
    corpus, _ = ingest_text("x.tf", 'resource "aws_s3_bucket" "b" {\n  acl = "private"\n}')
    assert len(corpus.resources) == 1
    assert corpus.resources[0]["type"] == "aws_s3_bucket"


# ---- fail-closed scanners -------------------------------------------------
def test_scanner_exception_fails_closed():
    @register("boom_scanner")
    def _boom(control, corpus):
        raise RuntimeError("kaboom")
    try:
        ctrl = Control(id="X", name="x", requirement="r", category="c",
                       pass_criteria=[], evidence_rule="e", scanner="boom_scanner")
        corpus, _ = ingest_text("x.tf", "")
        scan = run_scanner(ctrl, corpus)
        assert scan.has_violation                      # forces FAIL at the gate
        assert any(n.startswith(SCANNER_ERROR_NOTE) for n in scan.notes)
    finally:
        _REGISTRY.pop("boom_scanner", None)


# ---- worker error handling ------------------------------------------------
class _BoomEvaluateWorker:
    name = "boom-evaluate"
    def map_requirement(self, requirement, controls):
        return [c.id for c in controls]
    def evaluate(self, control, corpus, scan):
        raise RuntimeError("worker exploded")


class _BoomMapWorker:
    name = "boom-map"
    def map_requirement(self, requirement, controls):
        raise RuntimeError("mapping exploded")
    def evaluate(self, control, corpus, scan):  # pragma: no cover
        raise AssertionError("should not reach evaluate")


def test_worker_evaluate_failure_alarms_and_halts(tmp_path):
    rec = Harness(worker=_BoomEvaluateWorker(), runs_dir=tmp_path).run(
        FULL, "make this SOC 2 ready", "boom-eval")
    assert rec["errored"] is True
    assert rec["halted"] is True
    assert any(a["type"] == "WORKER_ERROR" for a in rec["alarms"])


def test_worker_map_failure_alarms_and_halts(tmp_path):
    rec = Harness(worker=_BoomMapWorker(), runs_dir=tmp_path).run(
        FULL, "make this SOC 2 ready", "boom-map")
    assert rec["errored"] is True
    assert rec["halted"] is True
    assert any(a["type"] == "WORKER_ERROR" for a in rec["alarms"])


# ---- WAL concurrent writes ------------------------------------------------
def test_concurrent_repo_writes_no_lock_errors(tmp_path):
    repo = RunRepository(tmp_path / "c.db")

    def _save(i):
        repo.save_run({
            "run_id": f"r{i}", "timestamp": float(i), "requirement": "x",
            "target": "t", "worker": "stub", "decision": "NO-SHIP",
            "halted": False, "escalations": [], "findings": [], "alarms": [],
            "risk": {"score": 1}, "metrics": {},
        })

    with ThreadPoolExecutor(max_workers=12) as ex:
        list(ex.map(_save, range(60)))

    assert len(repo.list_runs(limit=100)) == 60
