"""End-to-end smoke: the two bundled demos behave as the worked example says."""
from __future__ import annotations

from policy_to_proof.loop.orchestrator import Harness
from policy_to_proof.worker import get_worker


def _run(target, tmp_path, run_id):
    harness = Harness(worker=get_worker("stub"), runs_dir=tmp_path)
    return harness.run(target, "make this app SOC 2 ready before deployment", run_id)


def test_full_demo_is_no_ship(tmp_path):
    rec = _run("policy_to_proof/examples/full_demo", tmp_path, "full")
    assert rec["decision"] == "NO-SHIP"          # wildcard IAM + unencrypted storage
    assert rec["findings"]
    assert any(a["type"] == "CONTROL_FAILED" for a in rec["alarms"])


def test_halt_demo_trips_secret_exposed_and_halts(tmp_path):
    rec = _run("policy_to_proof/examples/halt_demo", tmp_path, "halt")
    assert rec["halted"] is True
    assert any(a["type"] == "SECRET_EXPOSED" for a in rec["alarms"])
    assert rec["decision"] == "NO-SHIP"
    # No PASS may be issued once the run halts on a critical secret.
    assert rec["findings"] == []
