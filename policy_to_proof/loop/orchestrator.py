"""PILLAR 1 — CHAT / LOOP: the orchestrator. This is the harness's train of thought.

It mirrors the deck's agent-loop skeleton ("keep calling the model, feeding back
results, until done or capped") — but specialized for compliance proof. Each
control is one pass through the loop:

    build context (control + corpus)
      -> call ENGINE (worker judgment)        [Pillar: worker, wrapped by guardrails]
      -> run TOOL (deterministic scanner)     [Pillar 2: tools]
      -> apply GUARDRAILS (no unproven PASS)   [Pillar 3: guardrails]
      -> run CHECKPOINTS (evidence/remediation gates)  [Pillar 1: stop/branch]
      -> EMIT spans + ALARMS, persist          [Pillar 4: observability]
    stop when all controls resolved OR a halting alarm (SECRET_EXPOSED) fires.

Hard limits (the deck's "stop condition matters as much as the steps"): a per-run
control cap prevents runaway loops.
"""
from __future__ import annotations

from ..types import Control, ScanCorpus
from ..guardrails.guardrails import Guardrails
from ..tools.ingest import ingest_path
from ..tools.registry import run_scanner
from ..tools import evidence as evidence_tool
from ..observability.alarms import AlarmBus
from ..observability.tracer import Tracer
from ..observability.store import RunStore
from ..worker import get_worker, Worker
from . import checkpoints as cp

MAX_CONTROLS_PER_RUN = 25  # hard limit / loop cap


class Harness:
    def __init__(self, worker: Worker | None = None,
                 controls_path=None, runs_dir=None,
                 clock=None) -> None:
        self.guardrails = Guardrails(controls_path) if controls_path else Guardrails()
        self.worker = worker or get_worker("auto")
        self.tracer = Tracer(clock) if clock else Tracer()
        self.store = RunStore(runs_dir) if runs_dir else RunStore()
        self._now = clock or __import__("time").time

    # ------------------------------------------------------------------
    def run(self, target_path: str, requirement: str, run_id: str) -> dict:
        alarms = AlarmBus()
        record: dict = {
            "run_id": run_id, "timestamp": self._now(), "requirement": requirement,
            "target": target_path, "worker": self.worker.name,
            "checkpoints": [], "findings": [], "alarms": [], "spans": [],
            "halted": False, "escalations": [],
        }

        # --- TOOL: ingest material (read-only) + GUARDRAIL: redact on the way in
        self.guardrails.assert_read_only()
        with self.tracer.span("tool.ingest", target=target_path) as sp:
            corpus, secret_hits = ingest_path(target_path)
            sp.attributes["resources"] = len(corpus.resources)
            sp.attributes["redactions"] = len(secret_hits)
        self.guardrails.assert_corpus_redacted(corpus)

        # --- ALARM (critical): any hardcoded secret halts the run immediately
        for hit in secret_hits:
            alarms.raise_alarm("SECRET_EXPOSED",
                               {"rule": hit.rule, "file": hit.file, "line": hit.line})
        if alarms.must_halt:
            record["halted"] = True
            record["alarms"] = alarms.to_list()
            self._finalize(record, halted=True)
            return record

        # --- CHECKPOINT: parse_gate (requirement -> controls) ; else escalate (HITL)
        controls = list(self.guardrails.controls.values())
        with self.tracer.span("loop.parse_gate"):
            mapped_ids = self.worker.map_requirement(requirement, controls)
            parse = cp.parse_gate(requirement, mapped_ids)
        record["checkpoints"].append(parse.to_dict())
        if parse.escalate:
            alarms.raise_alarm("UNMAPPED_REQUIREMENT", {"requirement": requirement})
            record["escalations"].append("parse_gate: no control maps to requirement")
            record["alarms"] = alarms.to_list()
            self._finalize(record, halted=False)
            return record

        in_scope = [c for c in controls if c.id in mapped_ids][:MAX_CONTROLS_PER_RUN]

        # --- THE LOOP: one pass per control
        for control in in_scope:
            self.guardrails.assert_in_scope(control.id)
            finding = self._evaluate_one(control, corpus, alarms)
            record["findings"].append(finding.to_dict())
            if alarms.must_halt:                      # stop condition
                record["halted"] = True
                break

        # --- CHECKPOINT: control_gate (all resolved)
        findings_objs = self._rehydrate(record["findings"])
        record["checkpoints"].append(cp.control_gate(findings_objs).to_dict())

        record["alarms"] = alarms.to_list()
        self._finalize(record, halted=record["halted"])
        return record

    # ------------------------------------------------------------------
    def _evaluate_one(self, control: Control, corpus: ScanCorpus, alarms: AlarmBus):
        # TOOL: deterministic scan (the checking)
        with self.tracer.span("tool.scan", control=control.id) as sp:
            scan = run_scanner(control, corpus)
            sp.attributes["proofs"] = len(scan.proofs)
            sp.attributes["violations"] = len(scan.violations)

        # ENGINE: worker judgment (wrapped by guardrails + a span)
        with self.tracer.span("llm.evaluate", control=control.id) as sp:
            finding = self.worker.evaluate(control, corpus, scan)
            sp.attributes["proposed_status"] = finding.status
            sp.attributes["confidence"] = finding.confidence

        # GUARDRAIL: no unproven PASS (+ confidence floor)
        finding, events = self.guardrails.enforce_finding(finding, scan)
        for ev in events:
            if "low_confidence" in ev:
                alarms.raise_alarm("LOW_CONFIDENCE_FINDING",
                                   {"control_id": control.id, "detail": ev})

        # CHECKPOINT: evidence_gate is the PASS authority
        eg = cp.evidence_gate(finding, scan)
        if eg.status == "FAIL" and finding.status == "PASS":
            finding.status = "FAIL"   # enforce downgrade
            alarms.raise_alarm("EVIDENCE_MISSING",
                               {"control_id": control.id, **eg.details})

        # alarms for substantive failures / insecure defaults
        if finding.status == "FAIL":
            if any("encrypt" in v.snippet.lower() or "unset" in v.snippet.lower()
                   for v in scan.violations):
                alarms.raise_alarm("INSECURE_DEFAULT",
                                   {"control_id": control.id})
            alarms.raise_alarm("CONTROL_FAILED",
                               {"control_id": control.id,
                                "violations": len(scan.violations)})

        # CHECKPOINT: remediation_gate for FAILs
        rg = cp.remediation_gate(finding)

        return finding

    # ------------------------------------------------------------------
    def _rehydrate(self, finding_dicts: list[dict]):
        from types import SimpleNamespace
        return [SimpleNamespace(**{k: d[k] for k in ("control_id", "status")})
                for d in finding_dicts]

    def _finalize(self, record: dict, halted: bool) -> None:
        risk = evidence_tool.risk_score(record["findings"]) if record["findings"] \
            else {"score": 0, "decision": "NO-SHIP", "critical_fail": halted}
        if halted:
            risk = {"score": 0, "decision": "NO-SHIP", "critical_fail": True}
        record["risk"] = risk
        record["metrics"] = self.tracer.metrics()
        record["spans"] = self.tracer.to_list()
        # CICD control proof: a persisted, gated decision now exists for this run.
        record["decision"] = risk["decision"]
        self.store.save(record["run_id"], record)

    # ------------------------------------------------------------------
    def replay(self, run_id: str, from_gate: str | None = None) -> dict:
        """Replay a persisted run from disk. With `from_gate`, return that gate's
        result without re-running prior stages (checkpoint replay requirement)."""
        record = self.store.load(run_id)
        if from_gate:
            cp_result = self.store.checkpoint(run_id, from_gate)
            return {"run_id": run_id, "from_gate": from_gate, "checkpoint": cp_result,
                    "findings": record["findings"], "decision": record.get("decision")}
        return record
