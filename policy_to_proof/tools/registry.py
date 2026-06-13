"""PILLAR 2 — TOOLS. The deterministic checkers, as typed tools.

In the harness anatomy, a Tool is a typed function the harness invokes: a schema,
an executor, and a predictable result contract. Here each scanner tool takes
(control, corpus) and returns a ControlScan of verifiable artifacts: `proofs`
(support a PASS) and `violations` (force a FAIL).

DESIGN PRINCIPLE: tools do the checking; the agent (engine) only does judgment.
No model is involved in this file — this is the checkov/tfsec/gitleaks-style
deterministic layer that gives the agent its hands.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
from ..types import Control, EvidenceRef, ScanCorpus

# Marker note prefix the orchestrator looks for to raise a SCANNER_ERROR alarm.
SCANNER_ERROR_NOTE = "scanner_error:"


@dataclass
class ControlScan:
    control_id: str
    proofs: list[EvidenceRef] = field(default_factory=list)
    violations: list[EvidenceRef] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def has_proof(self) -> bool:
        return len(self.proofs) > 0

    @property
    def has_violation(self) -> bool:
        return len(self.violations) > 0

    def to_dict(self) -> dict:
        return {
            "control_id": self.control_id,
            "proofs": [p.to_dict() for p in self.proofs],
            "violations": [v.to_dict() for v in self.violations],
            "notes": self.notes,
        }


# Tool registry: tool-name -> callable(control, corpus) -> ControlScan
# This is the tool "schema" layer: controls.yaml names the tool, the harness
# resolves and executes it, and the ControlScan is the result contract.
_REGISTRY: dict[str, Callable[[Control, ScanCorpus], ControlScan]] = {}


def register(name: str):
    def deco(fn: Callable[[Control, ScanCorpus], ControlScan]):
        _REGISTRY[name] = fn
        return fn
    return deco


def run_scanner(control: Control, corpus: ScanCorpus) -> ControlScan:
    fn = _REGISTRY.get(control.scanner)
    if fn is None:
        return ControlScan(control_id=control.id,
                           notes=[f"no scanner registered for '{control.scanner}'"])
    try:
        return fn(control, corpus)
    except Exception as e:
        # FAIL-CLOSED: a scanner that blows up on hostile input must never crash the
        # run or silently pass the control. Emit a synthetic violation (forces FAIL at
        # the evidence gate) plus a marker note so the orchestrator alarms.
        return ControlScan(
            control_id=control.id,
            violations=[EvidenceRef(
                file=getattr(corpus, "source_root", "?"), line=0,
                snippet=f"scanner '{control.scanner}' errored: {type(e).__name__}",
                kind="violation")],
            notes=[f"{SCANNER_ERROR_NOTE} {type(e).__name__}: {e}"],
        )


# Import side-effect: register all built-in scanner tools.
from . import scan_terraform as _scan_terraform  # noqa: E402,F401
from . import scan_secrets as _scan_secrets       # noqa: E402,F401
