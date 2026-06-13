"""Shared, structured data shapes used across all four pillars.

These are intentionally plain dataclasses so they serialize cleanly to JSON for
checkpoint persistence / replay, and so the worker interface stays language- and
model-agnostic.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal, Optional
import time

Status = Literal["PASS", "FAIL", "N_A"]
Severity = Literal["critical", "high", "medium", "low"]


@dataclass
class EvidenceRef:
    """A pointer to a verifiable artifact in the scanned material.

    `kind` distinguishes a proof (supports a PASS) from a violation (forces FAIL).
    Snippets are ALWAYS post-redaction.
    """
    file: str
    line: int
    snippet: str                       # redacted
    kind: Literal["proof", "violation"] = "proof"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Control:
    id: str
    name: str
    requirement: str
    category: str
    pass_criteria: list[str]
    evidence_rule: str
    scanner: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Finding:
    """The worker's judgment about a control. The worker MAY propose PASS, but the
    harness `evidence_gate` is the only authority that confirms PASS."""
    control_id: str
    status: Status
    evidence: list[EvidenceRef]
    confidence: float
    rationale: str = ""
    remediation: str = ""              # proposed diff / fix, drafted by the agent
    proposed_by: str = "unknown"       # which worker produced this (portability)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class Alarm:
    type: str                          # SECRET_EXPOSED, EVIDENCE_MISSING, ...
    context: dict
    severity: Severity
    recommended_action: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanCorpus:
    """Normalized, format-agnostic representation of ingested material.

    A Terraform parser feeds this today; a Kubernetes parser could feed the same
    shape tomorrow with zero changes downstream.
    """
    source_root: str
    files: dict[str, str]                       # path -> redacted text
    resources: list[dict]                       # normalized resource records
    config_map: dict                            # flattened key/value config view
    redactions: list[dict] = field(default_factory=list)  # what was redacted, where

    def to_dict(self) -> dict:
        return {
            "source_root": self.source_root,
            "files": list(self.files.keys()),   # don't dump full text into JSON evidence
            "resource_count": len(self.resources),
            "redaction_count": len(self.redactions),
        }
