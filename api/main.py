"""Policy-to-Proof HTTP API (FastAPI).

Endpoints:
  GET  /api/health                  -> liveness
  GET  /api/examples                -> bundled, allow-listed scan targets
  POST /api/scan                    -> run the harness on an allow-listed target
  GET  /api/runs                    -> run-history summaries (newest first)
  GET  /api/runs/{run_id}           -> full persisted record
  GET  /api/runs/{run_id}/packet    -> rendered evidence packet (CISO summary, matrix, diffs)
  GET  /api/runs/{run_id}/replay/{gate} -> replay one checkpoint from disk
  GET  /metrics                     -> Prometheus exposition (scraped by Prometheus/Grafana)

Safety: POST /api/scan only accepts targets on the bundled allow-list — the
harness never scans an arbitrary path supplied over the network.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from policy_to_proof.db.run_repository import RunRepository
from policy_to_proof.loop.orchestrator import Harness
from policy_to_proof.observability import metrics as prom
from policy_to_proof.tools import evidence as ev
from policy_to_proof.worker import get_worker

# Allow-listed scan targets — friendly name -> bundled path. No arbitrary paths.
EXAMPLES: dict[str, str] = {
    "full_demo": "policy_to_proof/examples/full_demo",
    "halt_demo": "policy_to_proof/examples/halt_demo",
}
EXAMPLE_BLURB: dict[str, str] = {
    "full_demo": "Wildcard IAM + unencrypted storage — completes as NO-SHIP with PR diffs.",
    "halt_demo": "Hardcoded secret — trips SECRET_EXPOSED and halts before any PASS.",
}

app = FastAPI(title="Policy-to-Proof", version="1.0")
repo = RunRepository()


class ScanRequest(BaseModel):
    target: str = "full_demo"
    requirement: str = "make this app SOC 2 ready before deployment"
    worker: str = "stub"
    run_id: str | None = None


def _summary(record: dict) -> dict:
    return {
        "run_id": record["run_id"],
        "decision": record.get("decision"),
        "risk": record.get("risk"),
        "halted": record.get("halted", False),
        "escalations": record.get("escalations", []),
        "worker": record.get("worker"),
        "alarms": record.get("alarms", []),
        "metrics": record.get("metrics", {}),
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/examples")
def examples() -> list[dict]:
    return [{"id": k, "path": v, "blurb": EXAMPLE_BLURB.get(k, "")}
            for k, v in EXAMPLES.items()]


@app.post("/api/scan")
def scan(req: ScanRequest) -> dict:
    if req.target not in EXAMPLES:
        raise HTTPException(
            status_code=400,
            detail=f"target must be one of {sorted(EXAMPLES)} (allow-list)")
    if req.worker not in ("stub", "claude", "auto"):
        raise HTTPException(status_code=400, detail="worker must be stub|claude|auto")

    run_id = req.run_id or f"web-{uuid.uuid4().hex[:8]}"
    harness = Harness(worker=get_worker(req.worker))
    record = harness.run(EXAMPLES[req.target], req.requirement, run_id)
    return {"summary": _summary(record), "packet": ev.render_packet(record)}


@app.get("/api/runs")
def runs(limit: int = 50) -> list[dict]:
    return repo.list_runs(limit=limit)


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict:
    record = repo.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown run '{run_id}'")
    return record


@app.get("/api/runs/{run_id}/packet")
def run_packet(run_id: str) -> dict:
    record = repo.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown run '{run_id}'")
    return {"summary": _summary(record), "packet": ev.render_packet(record)}


@app.get("/api/runs/{run_id}/replay/{gate}")
def run_replay(run_id: str, gate: str) -> dict:
    if repo.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown run '{run_id}'")
    return Harness().replay(run_id, from_gate=gate)


@app.get("/metrics")
def metrics() -> Response:
    body, content_type = prom.render()
    return Response(content=body, media_type=content_type)


# --- static web dashboard (added in the frontend layer) --------------------
_WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if _WEB_DIR.is_dir():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
