"""Deterministic stub worker — the portability proof + offline default.

Implements the exact same `Worker` interface as the Claude worker. It needs no
API key, so the whole harness runs in CI and demos without network. Swapping this
in for ClaudeWorker (or vice-versa) requires ZERO harness changes — that is the
SHOULD/BONUS "portability" requirement, demonstrable live.

It still only does JUDGMENT: it proposes a status from the scan, but the harness
guardrail/evidence checkpoint remains the sole authority on PASS.
"""
from __future__ import annotations

from ..types import Control, Finding, EvidenceRef, ScanCorpus
from ..tools.registry import ControlScan


class StubWorker:
    name = "stub-deterministic-v1"

    def map_requirement(self, requirement: str, controls: list[Control]) -> list[str]:
        req = requirement.lower()
        keywords = {
            "AC-LOG": ["log", "audit", "cloudtrail", "trail", "flow"],
            "IAM-LP": ["least privilege", "iam", "wildcard", "permission", "policy"],
            "SEC-MGMT": ["secret", "credential", "password", "key", "kms"],
            "ENC": ["encrypt", "tls", "at rest", "in transit", "kms"],
            "CICD": ["ci/cd", "cicd", "pipeline", "deploy", "gate", "soc 2", "soc2", "compliance"],
        }
        hits = [cid for cid, kws in keywords.items()
                if any(k in req for k in kws) and any(c.id == cid for c in controls)]
        # "soc 2 ready" style umbrella requirement => all controls in scope.
        if not hits and ("soc 2" in req or "soc2" in req or "compliant" in req or "ready" in req):
            return [c.id for c in controls]
        return hits

    def evaluate(self, control: Control, corpus: ScanCorpus,
                 scan: ControlScan) -> Finding:
        # Judgment from deterministic signal only.
        if scan.has_violation:
            status = "FAIL"
            confidence = 0.95
            rationale = (f"{len(scan.violations)} violation(s) found by deterministic "
                         f"scanner for {control.name}.")
        elif scan.has_proof:
            status = "PASS"      # proposed; evidence checkpoint will confirm
            confidence = 0.9
            rationale = f"{len(scan.proofs)} supporting artifact(s) and no violations."
        else:
            status = "N_A"
            confidence = 0.5
            rationale = f"No applicable resources found for {control.name}."

        remediation = self._draft_remediation(control, scan) if status == "FAIL" else ""
        evidence: list[EvidenceRef] = (scan.violations + scan.proofs)[:8]
        return Finding(
            control_id=control.id, status=status, evidence=evidence,
            confidence=confidence, rationale=rationale, remediation=remediation,
            proposed_by=self.name,
        )

    def _draft_remediation(self, control: Control, scan: ControlScan) -> str:
        templates = {
            "ENC": "# encrypt at rest\n storage_encrypted = true\n# or for S3, add aws_s3_bucket_server_side_encryption_configuration",
            "IAM-LP": '# replace wildcard with scoped actions/resources\n- "Action": "*"\n+ "Action": ["s3:GetObject", "s3:PutObject"]\n- "Resource": "*"\n+ "Resource": "arn:aws:s3:::my-bucket/*"',
            "SEC-MGMT": "# move secret to a manager\n- password = \"hardcoded\"\n+ password = data.aws_secretsmanager_secret_version.db.secret_string",
            "AC-LOG": '# add audit logging\nresource "aws_cloudtrail" "main" {\n  name           = "org-trail"\n  is_multi_region_trail = true\n}',
        }
        return templates.get(control.id, f"# remediate {control.name}: {control.pass_criteria[0]}")
