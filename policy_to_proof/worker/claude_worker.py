"""Claude worker — the default engine (Anthropic API).

Same `Worker` interface as the stub. The agent does JUDGMENT ONLY:
  - map_requirement: free-text requirement -> declared control_ids
  - evaluate: interpret deterministic scan output into a Finding + draft remediation

It is structurally incapable of asserting an unproven PASS: even if the model
returns PASS, the harness's guardrail + evidence checkpoint decide. The API key is
read from ANTHROPIC_API_KEY; it is never hardcoded. If the SDK or key is missing,
construction raises so the caller can fall back to the stub worker.
"""
from __future__ import annotations

import json
import os
from ..types import Control, Finding, EvidenceRef, ScanCorpus
from ..tools.registry import ControlScan

DEFAULT_MODEL = os.environ.get("POLICY_TO_PROOF_MODEL", "claude-opus-4-8")


class ClaudeWorker:
    name = "claude-anthropic"

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        try:
            from anthropic import Anthropic  # lazy import
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("anthropic SDK not installed (`pip install anthropic`)") from e
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self._client = Anthropic(api_key=key)
        self.model = model
        self.name = f"claude:{model}"

    # ---- requirement -> controls (judgment) ----------------------------
    def map_requirement(self, requirement: str, controls: list[Control]) -> list[str]:
        catalog = "\n".join(f"- {c.id}: {c.name} — {c.requirement.strip()}" for c in controls)
        prompt = (
            "You map a compliance requirement to declared controls. Respond with a "
            "JSON array of control_ids that apply (subset of the catalog). If none "
            "apply, return [].\n\n"
            f"Requirement:\n{requirement}\n\nControl catalog:\n{catalog}\n\n"
            "Return ONLY the JSON array."
        )
        text = self._complete(prompt, max_tokens=200)
        ids = self._extract_json(text, default=[])
        valid = {c.id for c in controls}
        return [i for i in ids if i in valid] if isinstance(ids, list) else []

    # ---- scan -> finding (judgment) ------------------------------------
    def evaluate(self, control: Control, corpus: ScanCorpus,
                 scan: ControlScan) -> Finding:
        proofs = [f"{p.file}:{p.line} {p.snippet}" for p in scan.proofs[:12]]
        violations = [f"{v.file}:{v.line} {v.snippet}" for v in scan.violations[:12]]
        prompt = (
            "You are a SOC 2 compliance judge. Deterministic scanners have already "
            "checked the config — you only INTERPRET their output. You MUST NOT "
            "invent evidence. Return strict JSON: "
            '{"status": "PASS|FAIL|N_A", "confidence": 0.0-1.0, "rationale": "...", '
            '"remediation": "unified-diff or terraform snippet, empty if PASS/N_A"}.\n\n'
            f"Control {control.id} — {control.name}\n"
            f"Requirement: {control.requirement.strip()}\n"
            f"Pass criteria: {control.pass_criteria}\n\n"
            f"Scanner PROOFS (support PASS):\n" + ("\n".join(proofs) or "(none)") + "\n\n"
            f"Scanner VIOLATIONS (force FAIL):\n" + ("\n".join(violations) or "(none)") + "\n\n"
            "Rules: if any violation exists, status must be FAIL. If no applicable "
            "resources exist, status is N_A. Only propose PASS when there is at least "
            "one proof and zero violations. Return ONLY the JSON object."
        )
        text = self._complete(prompt, max_tokens=800)
        data = self._extract_json(text, default={})
        status = data.get("status", "FAIL") if isinstance(data, dict) else "FAIL"
        if status not in ("PASS", "FAIL", "N_A"):
            status = "FAIL"
        confidence = float(data.get("confidence", 0.5)) if isinstance(data, dict) else 0.5
        evidence: list[EvidenceRef] = (scan.violations + scan.proofs)[:8]
        return Finding(
            control_id=control.id, status=status, evidence=evidence,
            confidence=max(0.0, min(1.0, confidence)),
            rationale=str(data.get("rationale", "")) if isinstance(data, dict) else "",
            remediation=str(data.get("remediation", "")) if isinstance(data, dict) else "",
            proposed_by=self.name,
        )

    # ---- helpers -------------------------------------------------------
    def _complete(self, prompt: str, max_tokens: int) -> str:
        resp = self._client.messages.create(
            model=self.model, max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(getattr(b, "text", "") for b in resp.content)

    @staticmethod
    def _extract_json(text: str, default):
        text = text.strip()
        # strip markdown fences if present
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json").strip()
        try:
            return json.loads(text)
        except Exception:
            # find first {...} or [...]
            for opener, closer in (("{", "}"), ("[", "]")):
                i, j = text.find(opener), text.rfind(closer)
                if i >= 0 and j > i:
                    try:
                        return json.loads(text[i:j + 1])
                    except Exception:
                        pass
            return default
