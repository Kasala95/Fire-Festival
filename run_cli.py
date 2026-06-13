#!/usr/bin/env python3
"""Policy-to-Proof CLI — run the harness as a CI/CD deployment gate.

Exit code 0 = SHIP, 1 = NO-SHIP/halt, 2 = escalation required. This makes the
harness itself usable as the CICD control: drop it in a pipeline and gate deploy
on the exit code.
"""
from __future__ import annotations

import argparse
import json
import sys

from policy_to_proof.loop.orchestrator import Harness
from policy_to_proof.worker import get_worker
from policy_to_proof.tools import evidence as ev


def main() -> int:
    ap = argparse.ArgumentParser(description="Policy-to-Proof compliance harness")
    ap.add_argument("--target", help="Terraform file or directory (required unless --replay)")
    ap.add_argument("--requirement", default="make this app SOC 2 ready before deployment")
    ap.add_argument("--worker", default="auto", choices=["auto", "claude", "stub"])
    ap.add_argument("--run-id", default="cli-run")
    ap.add_argument("--json", action="store_true", help="print raw run record as JSON")
    ap.add_argument("--replay", metavar="GATE", help="replay persisted run from a gate")
    args = ap.parse_args()

    harness = Harness(worker=get_worker(args.worker))

    if args.replay:
        out = harness.replay(args.run_id, from_gate=args.replay)
        print(json.dumps(out, indent=2, default=str))
        return 0

    if not args.target:
        ap.error("--target is required unless --replay is used")

    record = harness.run(args.target, args.requirement, args.run_id)

    if args.json:
        print(json.dumps(record, indent=2, default=str))
        return _exit_code(record)

    packet = ev.render_packet(record)
    print(packet["ciso_summary_md"])
    print("\n" + packet["control_matrix_md"])
    if record["alarms"]:
        print("\n## Alarms")
        for a in record["alarms"]:
            print(f"- [{a['severity'].upper()}] {a['type']}: {a['recommended_action']}")
    if record.get("escalations"):
        print("\n## Escalations (human-in-the-loop)")
        for e in record["escalations"]:
            print(f"- {e}")
    print(f"\nRun persisted to runs/{record['run_id']}.json")
    return _exit_code(record)


def _exit_code(record: dict) -> int:
    if record.get("escalations"):
        return 2
    return 0 if record.get("decision") == "SHIP" else 1


if __name__ == "__main__":
    sys.exit(main())
