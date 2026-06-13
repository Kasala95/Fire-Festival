"""Secret-redaction lane.

Detected secrets are redacted from text BEFORE anything reaches the agent or the
logs. This is part of material handling, but the *detection* findings are also
surfaced to the secrets scanner so the harness can raise a SECRET_EXPOSED alarm.

gitleaks-style regexes — deterministic, no model involved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# (name, compiled pattern, group index holding the secret value)
SECRET_PATTERNS: list[tuple[str, re.Pattern, int]] = [
    ("aws_access_key_id", re.compile(r"(AKIA[0-9A-Z]{16})"), 1),
    ("aws_secret_access_key",
     re.compile(r"(?i)aws_secret_access_key\s*=\s*[\"']?([A-Za-z0-9/+=]{40})[\"']?"), 1),
    ("generic_secret_key",
     re.compile(r"(?i)(?:secret|password|passwd|pwd|token|api_key|apikey)\s*[=:]\s*[\"']([^\"'\s]{8,})[\"']"), 1),
    ("private_key_block",
     re.compile(r"(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"), 1),
    ("slack_token", re.compile(r"(xox[baprs]-[0-9A-Za-z-]{10,})"), 1),
    ("github_pat", re.compile(r"(ghp_[0-9A-Za-z]{36})"), 1),
]


@dataclass
class SecretHit:
    rule: str
    file: str
    line: int
    redacted_line: str   # the line with the secret masked


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "****REDACTED****"
    return f"{value[:3]}…REDACTED…{value[-2:]}"


def redact_text(file_path: str, text: str) -> tuple[str, list[SecretHit]]:
    """Return (redacted_text, hits). Idempotent and deterministic."""
    hits: list[SecretHit] = []
    lines = text.splitlines()
    for idx, line in enumerate(lines, start=1):
        new_line = line
        for rule, pattern, group in SECRET_PATTERNS:
            for m in pattern.finditer(line):
                secret = m.group(group)
                new_line = new_line.replace(secret, _mask(secret))
                hits.append(SecretHit(rule=rule, file=file_path, line=idx,
                                      redacted_line=new_line.strip()))
        lines[idx - 1] = new_line
    return "\n".join(lines), hits
