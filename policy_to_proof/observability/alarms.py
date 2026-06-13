"""Alarms pillar — structured events.

Every alarm is {type, context, severity, recommended_action}. Alarm *types* and
their severities/actions are declared here so triage is deterministic, not
improvised by the agent.
"""
from __future__ import annotations

from ..types import Alarm

# Declared alarm catalog: type -> (severity, default recommended_action, halts_run)
CATALOG: dict[str, tuple[str, str, bool]] = {
    "SECRET_EXPOSED":       ("critical", "Halt run. Rotate the exposed credential immediately and remove from source.", True),
    "EVIDENCE_MISSING":     ("high",     "Cannot certify PASS without an artifact. Escalate to a human reviewer.", False),
    "CONTROL_FAILED":       ("high",     "Generate a remediation PR targeting the failed control.", False),
    "INSECURE_DEFAULT":     ("medium",   "Set the secure value explicitly (e.g. encrypted = true).", False),
    "UNMAPPED_REQUIREMENT": ("medium",   "No control maps to this requirement. Escalate to a human (HITL).", False),
    "LOW_CONFIDENCE_FINDING": ("low",    "Worker confidence below threshold. Route to human review.", False),
    "LIMIT_EXCEEDED":         ("high",    "Bounded-loop cap hit (tokens/time). Halt and review run scope.", True),
    "WORKER_ERROR":           ("critical", "The judgment engine (worker) failed. Halt the run; do not certify on a broken engine.", True),
    "SCANNER_ERROR":          ("high",    "A deterministic scanner errored; the control was failed closed. Investigate the input/scanner.", False),
    "INPUT_REJECTED":         ("medium",  "Input violated a guardrail (too large / too many resources). Reduce the material and retry.", False),
}


class AlarmBus:
    """Collects alarms during a run and reports whether the run must halt."""

    def __init__(self) -> None:
        self.alarms: list[Alarm] = []

    def raise_alarm(self, atype: str, context: dict,
                    recommended_action: str | None = None) -> Alarm:
        severity, default_action, _halts = CATALOG.get(
            atype, ("medium", "Review.", False))
        alarm = Alarm(
            type=atype,
            context=context,
            severity=severity,  # type: ignore[arg-type]
            recommended_action=recommended_action or default_action,
        )
        self.alarms.append(alarm)
        return alarm

    @property
    def must_halt(self) -> bool:
        return any(CATALOG.get(a.type, ("", "", False))[2] for a in self.alarms)

    def of_type(self, atype: str) -> list[Alarm]:
        return [a for a in self.alarms if a.type == atype]

    def to_list(self) -> list[dict]:
        return [a.to_dict() for a in self.alarms]
