"""Claude eval: graded against the same deterministic ground truth.

Opt-in — skipped unless ANTHROPIC_API_KEY is set (it makes real API calls).
"""
from __future__ import annotations

import os

import pytest

from evals.run_evals import CLAUDE_BAR, score


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"),
                    reason="needs ANTHROPIC_API_KEY (live Claude calls)")
def test_claude_meets_bar():
    result = score("claude")
    assert result["pass_rate"] >= CLAUDE_BAR, result["per_file"]
