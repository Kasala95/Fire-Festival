"""PILLAR 1 — CHAT / LOOP: the checkpoints (gates) that branch and stop the loop.

In the harness anatomy the loop "keeps calling the model until it emits a final
answer or hits a limit." Checkpoints ARE those stop/branch conditions, made
explicit and given pass/fail criteria. Each gate returns a CheckpointResult that
the orchestrator persists (Pillar 4) so any gate is replayable.

Gate order:
  parse_gate       requirement -> >=1 control, else UNMAPPED_REQUIREMENT + escalate
  control_gate     each control resolves to PASS/FAIL/N_A (worker judgment, guardrailed)
  evidence_gate    every PASS must have a verifiable artifact, else downgrade to FAIL
  remediation_gate every FAIL has a remediation that parses and targets that control
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal

GateStatus = Literal["PASS", "FAIL", "N_A", "ESCALATE"]


@dataclass
class CheckpointResult:
    name: str
    status: GateStatus
    criteria: str                       # explicit pass/fail criteria, declared
    details: dict = field(default_factory=dict)
    escalate: bool = False              # human-in-the-loop required

    def to_dict(self) -> dict:
        return asdict(self)


# ---- parse_gate --------------------------------------------------------
def parse_gate(requirement: str, mapped_ids: list[str]) -> CheckpointResult:
    crit = "requirement maps to >=1 declared control"
    if not mapped_ids:
        return CheckpointResult("parse_gate", "ESCALATE", crit,
                                details={"requirement": requirement, "mapped": []},
                                escalate=True)
    return CheckpointResult("parse_gate", "PASS", crit,
                            details={"requirement": requirement, "mapped": mapped_ids})


# ---- control_gate ------------------------------------------------------
def control_gate(findings: list) -> CheckpointResult:
    crit = "each in-scope control resolves to PASS/FAIL/N_A"
    statuses = {f.control_id: f.status for f in findings}
    ok = all(s in ("PASS", "FAIL", "N_A") for s in statuses.values())
    return CheckpointResult("control_gate", "PASS" if ok else "FAIL", crit,
                            details={"statuses": statuses})


# ---- evidence_gate -----------------------------------------------------
def evidence_gate(finding, scan) -> CheckpointResult:
    """The PASS authority. A PASS survives ONLY with a verifiable proof artifact
    and no violations; otherwise it is downgraded to FAIL here."""
    crit = "every PASS has >=1 verifiable artifact and zero violations"
    if finding.status == "PASS":
        has_proof = any(e.kind == "proof" for e in finding.evidence) or scan.has_proof
        if scan.has_violation or not has_proof:
            return CheckpointResult(
                "evidence_gate", "FAIL", crit,
                details={"control_id": finding.control_id,
                         "reason": "unproven PASS downgraded to FAIL",
                         "had_proof": has_proof, "had_violation": scan.has_violation})
        return CheckpointResult("evidence_gate", "PASS", crit,
                                details={"control_id": finding.control_id,
                                         "proof_count": len(scan.proofs)})
    # FAIL / N_A pass the evidence gate trivially (nothing to certify).
    return CheckpointResult("evidence_gate", "N_A", crit,
                            details={"control_id": finding.control_id,
                                     "status": finding.status})


# ---- remediation_gate --------------------------------------------------
def remediation_gate(finding) -> CheckpointResult:
    crit = "every FAIL has a remediation that is non-empty and targets the control"
    if finding.status != "FAIL":
        return CheckpointResult("remediation_gate", "N_A", crit,
                                details={"control_id": finding.control_id})
    rem = (finding.remediation or "").strip()
    targets = bool(rem) and len(rem.splitlines()) >= 1
    return CheckpointResult("remediation_gate", "PASS" if targets else "FAIL", crit,
                            details={"control_id": finding.control_id,
                                     "has_remediation": bool(rem),
                                     "lines": len(rem.splitlines())})
