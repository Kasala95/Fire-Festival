"""Bounded-loop caps: a tiny time budget must halt the run with LIMIT_EXCEEDED."""
from __future__ import annotations

from pathlib import Path

import yaml

from policy_to_proof.loop.orchestrator import Harness
from policy_to_proof.worker import get_worker

EXAMPLE = "policy_to_proof/examples/full_demo"


def _controls_with_caps(tmp_path, **caps) -> Path:
    """Copy controls.yaml but override the cap values to force a halt."""
    src = Path("policy_to_proof/controls.yaml")
    doc = yaml.safe_load(src.read_text())
    doc["guardrails"].update(caps)
    out = tmp_path / "controls.yaml"
    out.write_text(yaml.safe_dump(doc))
    return out


def test_time_cap_halts_with_limit_exceeded(tmp_path):
    controls = _controls_with_caps(tmp_path, max_seconds_per_run=0.0001)
    harness = Harness(worker=get_worker("stub"),
                      controls_path=controls, runs_dir=tmp_path)
    record = harness.run(EXAMPLE, "make this SOC 2 ready", run_id="capped")

    assert record["halted"] is True
    assert any(a["type"] == "LIMIT_EXCEEDED" for a in record["alarms"])
    assert record["decision"] == "NO-SHIP"


def test_no_cap_completes_normally(tmp_path):
    # Generous caps -> the run finishes, no LIMIT_EXCEEDED.
    controls = _controls_with_caps(tmp_path, max_seconds_per_run=600,
                                   max_tokens_per_run=10_000_000)
    harness = Harness(worker=get_worker("stub"),
                      controls_path=controls, runs_dir=tmp_path)
    record = harness.run(EXAMPLE, "make this SOC 2 ready", run_id="uncapped")

    assert not any(a["type"] == "LIMIT_EXCEEDED" for a in record["alarms"])
    assert record["findings"]   # controls were evaluated
