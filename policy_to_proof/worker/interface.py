"""The ENGINE contract.

In the harness anatomy: "the model is the engine, the harness is the car." The
worker IS the engine. It sits inside the loop (Pillar 1) and is wrapped by
guardrails (Pillar 3) and watched by observability (Pillar 4).

A Worker receives `control + corpus + scan` (the deterministic tool output) and
returns a Finding — its JUDGMENT. It may *propose* PASS, but the harness's
evidence checkpoint is the only thing that can confirm one. Swapping models =
implementing this one method. Zero harness changes required.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from ..types import Control, Finding, ScanCorpus
from ..tools.registry import ControlScan


@runtime_checkable
class Worker(Protocol):
    name: str

    def evaluate(self, control: Control, corpus: ScanCorpus,
                 scan: ControlScan) -> Finding:
        """Interpret deterministic scan output into a Finding (judgment only)."""
        ...

    def map_requirement(self, requirement: str, controls: list[Control]) -> list[str]:
        """Map a free-text requirement to >=1 declared control_id. Empty => unmapped."""
        ...
