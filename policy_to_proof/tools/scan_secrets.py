"""Secrets-management scanner (control SEC-MGMT).

Uses the same gitleaks-style patterns as the redaction lane. Because redaction
already masked secrets in the corpus, we re-run detection over the recorded
redaction list (which preserved location) and check for KMS / secrets-manager
references as positive proof.
"""
from __future__ import annotations

from ..types import Control, EvidenceRef, ScanCorpus
from .registry import ControlScan, register

_KMS_HINTS = ("aws_kms_key", "kms_key_id", "kms_master_key_id",
              "aws_secretsmanager_secret", "ssm:", "data.aws_secretsmanager")


@register("secrets")
def scan_secrets(control: Control, corpus: ScanCorpus) -> ControlScan:
    scan = ControlScan(control_id=control.id)

    # Violations: every redaction hit recorded during ingest is a hardcoded secret.
    for red in corpus.redactions:
        scan.violations.append(EvidenceRef(
            file=red["file"], line=red["line"],
            snippet=f"hardcoded secret detected ({red['rule']}) — value redacted",
            kind="violation",
        ))

    # Proofs: KMS / secrets-manager references.
    for path, text in corpus.files.items():
        for lineno, line in enumerate(text.splitlines(), start=1):
            low = line.lower()
            if any(h in low for h in _KMS_HINTS):
                scan.proofs.append(EvidenceRef(
                    file=path, line=lineno, snippet=line.strip(), kind="proof"))

    if not scan.proofs and not scan.violations:
        scan.notes.append("no secrets and no KMS/secrets-manager references found")
    return scan
