"""The swappable engine. Selecting one requires zero harness changes."""
from __future__ import annotations

from .interface import Worker
from .stub_worker import StubWorker


def get_worker(prefer: str = "auto") -> Worker:
    """Return a Worker. `prefer`: 'claude' | 'stub' | 'auto'.

    'auto' uses Claude when ANTHROPIC_API_KEY + SDK are available, else the stub.
    The rest of the harness never branches on which engine it got.
    """
    if prefer in ("claude", "auto"):
        try:
            from .claude_worker import ClaudeWorker
            return ClaudeWorker()
        except Exception:
            if prefer == "claude":
                raise
    return StubWorker()


__all__ = ["Worker", "StubWorker", "get_worker"]
