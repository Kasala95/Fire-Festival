"""Guardrails pillar — declared rules, enforced AROUND the agent.

Constraint-handling is invisible to the agent: the worker receives `control +
corpus` and returns a Finding. This module decides what is allowed, what may pass,
and what trips an alarm. The agent cannot opt out of any of this.

Guardrails enforced here:
  1. scope_lock        — worker may only evaluate declared control_ids
  2. no_unproven_pass  — a PASS is downgraded to FAIL unless a scanner proof exists
  3. read_only_target  — the harness never writes to the scanned target
  4. redact_secrets    — verified at the boundary (corpus must be pre-redacted)
  5. confidence floor  — low-confidence findings are flagged for human review
"""
from __future__ import annotations

import yaml
from pathlib import Path
from ..types import Control, Finding, ScanCorpus
from ..tools.registry import ControlScan

CONTROLS_PATH = Path(__file__).resolve().parent.parent / "controls.yaml"


class Guardrails:
    def __init__(self, controls_path: Path | str = CONTROLS_PATH) -> None:
        with open(controls_path, "r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        self.config: dict = doc.get("guardrails", {})
        self.controls: dict[str, Control] = {}
        for c in doc.get("controls", []):
            self.controls[c["id"]] = Control(
                id=c["id"], name=c["name"], requirement=c["requirement"],
                category=c["category"], pass_criteria=c["pass_criteria"],
                evidence_rule=c["evidence_rule"], scanner=c["scanner"])

    # ---- scope lock -----------------------------------------------------
    def is_in_scope(self, control_id: str) -> bool:
        if not self.config.get("scope_lock", True):
            return True
        return control_id in self.controls

    def assert_in_scope(self, control_id: str) -> None:
        if not self.is_in_scope(control_id):
            raise PermissionError(
                f"scope_lock: '{control_id}' is not a declared control. "
                f"Allowed: {sorted(self.controls)}")

    # ---- read-only target ----------------------------------------------
    def assert_read_only(self) -> bool:
        # The harness opens target files read-only by construction (see ingest).
        return bool(self.config.get("read_only_target", True))

    # ---- redaction boundary --------------------------------------------
    def assert_corpus_redacted(self, corpus: ScanCorpus) -> None:
        if not self.config.get("redact_secrets", True):
            return
        # Boundary check: any recorded secret must not appear verbatim in files.
        # (redaction already masked them; this asserts the invariant held.)
        for path, text in corpus.files.items():
            if "AKIA" in text and "REDACTED" not in text:
                raise AssertionError(f"redaction guardrail violated in {path}")

    # ---- the central enforcement: no unproven PASS ----------------------
    def enforce_finding(self, finding: Finding, scan: ControlScan) -> tuple[Finding, list[str]]:
        """Apply guardrails to a worker's proposed finding.

        Returns (possibly-mutated finding, list of guardrail events). The worker's
        PASS is only honored when the deterministic scanner produced a proof and
        no violation. Otherwise it is downgraded — the agent is structurally
        incapable of asserting an unproven PASS.
        """
        events: list[str] = []

        if self.config.get("no_unproven_pass", True) and finding.status == "PASS":
            if scan.has_violation:
                finding.status = "FAIL"
                events.append("no_unproven_pass: PASS downgraded to FAIL (scanner found violations)")
            elif not scan.has_proof:
                finding.status = "FAIL"
                events.append("no_unproven_pass: PASS downgraded to FAIL (no verifiable artifact)")

        floor = float(self.config.get("max_worker_confidence_for_auto", 0.6))
        if finding.confidence < floor:
            events.append(f"low_confidence: {finding.confidence:.2f} < {floor:.2f} -> human review")

        return finding, events
