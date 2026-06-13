#!/usr/bin/env python3
"""Evals — score the harness against a golden corpus.

Each golden .tf has an expected verdict (per-control status + decision + halted +
key alarms) in expected.yaml, captured from the verified deterministic output.

  python evals/run_evals.py            # score the stub worker (deterministic ground truth)
  python evals/run_evals.py --worker claude   # score Claude vs the same ground truth
  python evals/run_evals.py --bootstrap       # (re)generate expected.yaml from stub output

The stub must score 100% (it *is* the ground truth → a regression lock). Claude is
graded against the same expected and is allowed to miss a few (judgment varies).
Writes evals/last_result.json (read by /metrics for the live pass-rate gauge) and a
markdown report.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import tempfile
import time

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from policy_to_proof.loop.orchestrator import Harness
from policy_to_proof.worker import get_worker

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.join(HERE, "golden")
EXPECTED_PATH = os.path.join(GOLDEN_DIR, "expected.yaml")
RESULT_PATH = os.path.join(HERE, "last_result.json")
REPORT_PATH = os.path.join(HERE, "report.md")
REQUIREMENT = "make this app SOC 2 ready before deployment"
STUB_BAR = 1.0       # deterministic ground truth must be exact
CLAUDE_BAR = 0.90    # judgment engine: allowed to miss a few


def _golden_files() -> list[str]:
    return sorted(f for f in glob.glob(os.path.join(GOLDEN_DIR, "*.tf")))


def observe(path: str, worker_name: str) -> dict:
    """Run the harness on one golden file; return the normalized observation."""
    harness = Harness(worker=get_worker(worker_name), runs_dir=tempfile.mkdtemp())
    rec = harness.run(path, REQUIREMENT, run_id=os.path.basename(path))
    return {
        "decision": rec["decision"],
        "halted": bool(rec["halted"]),
        "controls": {x["control_id"]: x["status"] for x in rec["findings"]},
        "alarms": sorted({a["type"] for a in rec["alarms"]}),
    }


def bootstrap() -> None:
    """Capture current stub output as the expected ground truth."""
    expected = {os.path.basename(f): observe(f, "stub") for f in _golden_files()}
    with open(EXPECTED_PATH, "w", encoding="utf-8") as fh:
        yaml.safe_dump(expected, fh, sort_keys=True, default_flow_style=False)
    print(f"wrote {EXPECTED_PATH} ({len(expected)} files)")


def _checks(name: str, expected: dict, observed: dict) -> list[tuple[str, bool]]:
    """One (label, passed) per gradable assertion for a file."""
    out = [
        (f"{name}:decision", expected["decision"] == observed["decision"]),
        (f"{name}:halted", expected["halted"] == observed["halted"]),
    ]
    for cid, status in expected.get("controls", {}).items():
        out.append((f"{name}:{cid}", observed.get("controls", {}).get(cid) == status))
    # validate the critical secret-halt path when expected
    if "SECRET_EXPOSED" in expected.get("alarms", []):
        out.append((f"{name}:SECRET_EXPOSED", "SECRET_EXPOSED" in observed["alarms"]))
    return out


def score(worker_name: str) -> dict:
    with open(EXPECTED_PATH, encoding="utf-8") as fh:
        expected = yaml.safe_load(fh)

    files, all_checks, per_file = _golden_files(), [], {}
    for f in files:
        name = os.path.basename(f)
        exp = expected.get(name)
        if exp is None:
            continue
        obs = observe(f, worker_name)
        checks = _checks(name, exp, obs)
        per_file[name] = {
            "passed": sum(1 for _, ok in checks if ok), "total": len(checks),
            "mismatches": [label for label, ok in checks if not ok],
        }
        all_checks.extend(checks)

    passed = sum(1 for _, ok in all_checks if ok)
    total = len(all_checks) or 1
    return {
        "worker": worker_name,
        "files": len(per_file),
        "checks": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4),
        "per_file": per_file,
        "timestamp": time.time(),
    }


def write_outputs(result: dict) -> None:
    with open(RESULT_PATH, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    lines = [f"# Eval report — worker `{result['worker']}`", "",
             f"**Pass rate: {result['pass_rate']*100:.1f}%** "
             f"({result['passed']}/{result['checks']} checks, {result['files']} files)", ""]
    for name, fr in sorted(result["per_file"].items()):
        mark = "✅" if not fr["mismatches"] else "❌"
        lines.append(f"- {mark} `{name}` {fr['passed']}/{fr['total']}"
                     + (f" — misses: {', '.join(fr['mismatches'])}" if fr["mismatches"] else ""))
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Policy-to-Proof evals")
    ap.add_argument("--worker", default="stub", choices=["stub", "claude", "auto"])
    ap.add_argument("--bootstrap", action="store_true",
                    help="regenerate expected.yaml from current stub output")
    args = ap.parse_args()

    if args.bootstrap:
        bootstrap()
        return 0

    result = score(args.worker)
    write_outputs(result)
    bar = STUB_BAR if args.worker == "stub" else CLAUDE_BAR
    print(f"{args.worker}: pass_rate={result['pass_rate']*100:.1f}% "
          f"({result['passed']}/{result['checks']})  bar={bar*100:.0f}%")
    for name, fr in sorted(result["per_file"].items()):
        if fr["mismatches"]:
            print(f"  ✗ {name}: {', '.join(fr['mismatches'])}")
    return 0 if result["pass_rate"] >= bar else 1


if __name__ == "__main__":
    raise SystemExit(main())
