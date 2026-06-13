"""PILLAR 4 — OBSERVABILITY: structured spans + the four reliability signals.

"If you can't see it, you can't fix it." Every model and tool call is wrapped in
a span carrying the attributes the deck calls out: latency, token cost, errors,
and (per run) an eval/pass-rate. We emit lightweight in-process spans here so the
harness has zero external dependencies; the shape mirrors OpenTelemetry so it can
be swapped for a real OTel exporter without touching call sites.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict


@dataclass
class Span:
    name: str
    attributes: dict = field(default_factory=dict)
    start: float = 0.0
    duration_ms: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class Tracer:
    """Collects spans for one run and rolls up the four reliability signals."""

    def __init__(self, clock=time.time) -> None:
        self._clock = clock
        self.spans: list[Span] = []

    @contextmanager
    def span(self, name: str, **attributes):
        sp = Span(name=name, attributes=dict(attributes), start=self._clock())
        try:
            yield sp
        except Exception as e:
            sp.error = f"{type(e).__name__}: {e}"
            raise
        finally:
            sp.duration_ms = round((self._clock() - sp.start) * 1000, 2)
            self.spans.append(sp)

    # ---- the four signals the deck says move reliability ---------------
    def metrics(self) -> dict:
        durs = sorted(s.duration_ms for s in self.spans)
        p95 = durs[int(len(durs) * 0.95)] if durs else 0.0
        tokens_in = sum(s.attributes.get("tokens_in", 0) for s in self.spans)
        tokens_out = sum(s.attributes.get("tokens_out", 0) for s in self.spans)
        cost = sum(s.attributes.get("cost_usd", 0.0) for s in self.spans)
        errors = sum(1 for s in self.spans if s.error)
        tool_spans = [s for s in self.spans if s.name.startswith("tool.")]
        tool_errors = sum(1 for s in tool_spans if s.error)
        return {
            "p95_latency_ms": p95,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": round(cost, 4),
            "tool_error_rate": round(tool_errors / len(tool_spans), 3) if tool_spans else 0.0,
            "span_count": len(self.spans),
            "errors": errors,
        }

    def to_list(self) -> list[dict]:
        return [s.to_dict() for s in self.spans]
