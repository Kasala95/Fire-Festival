"""Evals: the stub worker is the deterministic ground truth -> must score 100%."""
from __future__ import annotations

from evals.run_evals import score


def test_stub_scores_perfect():
    result = score("stub")
    assert result["files"] >= 15                      # golden corpus present
    assert result["pass_rate"] == 1.0, result["per_file"]


def test_every_golden_file_has_expectation():
    result = score("stub")
    # no file should silently score zero checks (would mean a missing expectation)
    assert all(fr["total"] > 0 for fr in result["per_file"].values())
