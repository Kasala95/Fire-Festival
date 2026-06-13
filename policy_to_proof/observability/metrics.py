"""PILLAR 4 — OBSERVABILITY: Prometheus metrics for live dashboards.

The in-process Tracer (tracer.py) gives each *run* its own span trace and the
four reliability signals, persisted into the run record. This module is the
complementary *fleet* view: process-wide Prometheus counters/gauges that
Prometheus scrapes from the API's /metrics endpoint and Grafana charts over time.

`record_run(record)` is called once per finished run and updates every metric
from the run record. It is wrapped best-effort by the orchestrator, so a metrics
failure never breaks a run.
"""
from __future__ import annotations

import json
import os

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# Latest eval result (written by evals/run_evals.py) → surfaced as a live gauge.
_EVAL_RESULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "evals", "last_result.json")

# --- the metrics (process-wide) --------------------------------------------
RUNS_TOTAL = Counter(
    "p2p_runs_total", "Harness runs completed", ["decision", "worker"])
RUN_DURATION = Histogram(
    "p2p_run_duration_seconds", "Wall-clock duration of a run",
    buckets=(0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10, 30, 60))
LAST_RISK_SCORE = Gauge(
    "p2p_last_risk_score", "Risk score of the most recent run (0-100)")
ALARMS_TOTAL = Counter(
    "p2p_alarms_total", "Alarms raised", ["type", "severity"])
CONTROL_RESULTS_TOTAL = Counter(
    "p2p_control_results_total", "Per-control results", ["status"])
TOKENS_TOTAL = Counter(
    "p2p_tokens_total", "Model tokens consumed", ["direction"])
HALTS_TOTAL = Counter(
    "p2p_halts_total", "Runs halted by a critical alarm")
EVAL_PASS_RATE = Gauge(
    "p2p_eval_pass_rate", "Latest eval pass rate against the golden corpus (0-1)")
SCAN_DURATION = Histogram(
    "p2p_scan_duration_seconds", "Per-control deterministic scan duration", ["control"],
    buckets=(0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1))
INPUT_REJECTED_TOTAL = Counter(
    "p2p_input_rejected_total", "Inputs rejected by an input guardrail", ["reason"])


def record_run(record: dict) -> None:
    """Update all metrics from one finished run record."""
    decision = record.get("decision") or "UNKNOWN"
    worker = record.get("worker") or "unknown"
    RUNS_TOTAL.labels(decision=decision, worker=worker).inc()

    risk = (record.get("risk") or {}).get("score")
    if risk is not None:
        LAST_RISK_SCORE.set(risk)

    metrics = record.get("metrics") or {}
    if "run_seconds" in metrics:
        RUN_DURATION.observe(float(metrics["run_seconds"]))
    TOKENS_TOTAL.labels(direction="in").inc(metrics.get("tokens_in", 0))
    TOKENS_TOTAL.labels(direction="out").inc(metrics.get("tokens_out", 0))

    for finding in record.get("findings", []):
        CONTROL_RESULTS_TOTAL.labels(status=finding.get("status", "UNKNOWN")).inc()

    for alarm in record.get("alarms", []):
        atype = alarm.get("type", "UNKNOWN")
        ALARMS_TOTAL.labels(type=atype, severity=alarm.get("severity", "unknown")).inc()
        if atype == "INPUT_REJECTED":
            INPUT_REJECTED_TOTAL.labels(
                reason=alarm.get("context", {}).get("reason", "unknown")).inc()

    # per-control scan latency, read from the run's spans
    for span in record.get("spans", []):
        if span.get("name") == "tool.scan":
            control = span.get("attributes", {}).get("control", "unknown")
            SCAN_DURATION.labels(control=control).observe(
                float(span.get("duration_ms", 0)) / 1000.0)

    if record.get("halted"):
        HALTS_TOTAL.inc()


def _refresh_eval_gauge() -> None:
    """Update the eval pass-rate gauge from the last persisted eval result."""
    try:
        with open(_EVAL_RESULT_PATH, encoding="utf-8") as fh:
            EVAL_PASS_RATE.set(float(json.load(fh).get("pass_rate", 0.0)))
    except Exception:
        pass   # no eval result yet -> leave gauge at its current value


def render() -> tuple[bytes, str]:
    """Return (body, content_type) for the /metrics endpoint."""
    _refresh_eval_gauge()
    return generate_latest(), CONTENT_TYPE_LATEST
