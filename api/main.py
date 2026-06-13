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

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from policy_to_proof.db.run_repository import RunRepository
from policy_to_proof.loop.orchestrator import Harness
from policy_to_proof.observability import metrics as prom
from policy_to_proof.tools import evidence as ev
from policy_to_proof.tools.ingest import MAX_INPUT_BYTES
from policy_to_proof.worker import get_worker

# Hard ceiling on any request body (defense against a giant paste exhausting memory
# before our field-level check runs). Generous over the 512KB Terraform cap.
MAX_BODY_BYTES = 1_000_000

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
    # Field caps bound attacker-controlled strings at validation time (defense in
    # depth with the body-size middleware and the ingest byte cap).
    target: str = Field(default="full_demo", max_length=200)
    requirement: str = Field(
        default="make this app SOC 2 ready before deployment", max_length=2000)
    worker: str = Field(default="stub", max_length=16)
    terraform: str | None = Field(default=None, max_length=MAX_BODY_BYTES)
    # NOTE: no client-supplied run_id — the server always generates it, so a caller
    # cannot overwrite another run's record (INSERT OR REPLACE keys on run_id).


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_BODY_BYTES:
        prom.INPUT_REJECTED_TOTAL.labels(reason="body_too_large").inc()
        return JSONResponse(status_code=413, content={"detail": "request body too large"})
    return await call_next(request)


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
    if req.worker not in ("stub", "claude", "auto"):
        raise HTTPException(status_code=400, detail="worker must be stub|claude|auto")
    run_id = f"web-{uuid.uuid4().hex[:8]}"   # always server-generated
    harness = Harness(worker=get_worker(req.worker))

    # Pasted Terraform (public, hardened): scanned in memory, never written to disk.
    if req.terraform and req.terraform.strip():
        if len(req.terraform.encode("utf-8")) > MAX_INPUT_BYTES:
            prom.INPUT_REJECTED_TOTAL.labels(reason="input_too_large").inc()
            raise HTTPException(
                status_code=413,
                detail=f"pasted Terraform exceeds {MAX_INPUT_BYTES} bytes")
        record = harness.run_text("pasted.tf", req.terraform, req.requirement, run_id)
        if any(a["type"] == "INPUT_REJECTED" for a in record["alarms"]):
            raise HTTPException(
                status_code=413,
                detail="pasted Terraform rejected by an input guardrail")
        return {"summary": _summary(record), "packet": ev.render_packet(record)}

    # Bundled example (allow-listed path).
    if req.target not in EXAMPLES:
        raise HTTPException(
            status_code=400,
            detail=f"target must be one of {sorted(EXAMPLES)} (allow-list)")
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
