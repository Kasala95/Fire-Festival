"""PILLAR 2 — TOOLS (egress): render the evidence packet.

Turns the structured run record into the deliverables: a risk score, a control
matrix, a timestamped/source-linked evidence report, suggested PR diffs, and a
CISO executive summary. Markdown output so it renders in the UI and as a file.
"""
from __future__ import annotations

import time

_WEIGHTS = {"AC-LOG": 20, "IAM-LP": 25, "SEC-MGMT": 30, "ENC": 20, "CICD": 5}


def risk_score(findings: list[dict]) -> dict:
    """0 (worst) .. 100 (best) weighted posture score + ship/no-ship decision."""
    total = 0.0
    earned = 0.0
    for f in findings:
        w = _WEIGHTS.get(f["control_id"], 10)
        if f["status"] == "N_A":
            continue
        total += w
        if f["status"] == "PASS":
            earned += w
    score = round((earned / total) * 100) if total else 100
    has_critical_fail = any(
        f["status"] == "FAIL" and f["control_id"] in ("SEC-MGMT", "IAM-LP")
        for f in findings)
    decision = "NO-SHIP" if (score < 80 or has_critical_fail) else "SHIP"
    return {"score": score, "decision": decision,
            "critical_fail": has_critical_fail}


def control_matrix_md(findings: list[dict]) -> str:
    icon = {"PASS": "✅", "FAIL": "❌", "N_A": "➖"}
    rows = ["| Control | Status | Confidence | Evidence | By |",
            "|---|---|---|---|---|"]
    for f in findings:
        ev = f["evidence"][0] if f["evidence"] else None
        ev_s = f'`{ev["file"]}:{ev["line"]}`' if ev else "—"
        rows.append(f'| {f["control_id"]} | {icon.get(f["status"],"?")} {f["status"]} '
                    f'| {f["confidence"]:.2f} | {ev_s} | {f.get("proposed_by","?")} |')
    return "\n".join(rows)


def evidence_report_md(findings: list[dict], ts: float | None = None) -> str:
    ts = ts if ts is not None else time.time()
    stamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(ts))
    out = [f"## Evidence report\n_Generated {stamp}_\n"]
    for f in findings:
        out.append(f"### {f['control_id']} — {f['status']}")
        out.append(f"_{f.get('rationale','')}_\n")
        if f["evidence"]:
            for e in f["evidence"]:
                kind = e.get("kind", "proof")
                out.append(f"- **{kind}** `{e['file']}:{e['line']}` — {e['snippet']}")
        else:
            out.append("- _no artifacts_")
        out.append("")
    return "\n".join(out)


def pr_diffs_md(findings: list[dict]) -> str:
    out = ["## Suggested remediation (PR diffs)\n"]
    any_fail = False
    for f in findings:
        if f["status"] == "FAIL" and f.get("remediation"):
            any_fail = True
            out.append(f"### Fix {f['control_id']}\n```diff\n{f['remediation']}\n```\n")
    if not any_fail:
        out.append("_No failed controls require remediation._")
    return "\n".join(out)


def ciso_summary_md(findings: list[dict], risk: dict, alarms: list[dict]) -> str:
    n_pass = sum(1 for f in findings if f["status"] == "PASS")
    n_fail = sum(1 for f in findings if f["status"] == "FAIL")
    n_na = sum(1 for f in findings if f["status"] == "N_A")
    crit = [a for a in alarms if a["severity"] == "critical"]
    banner = "🚫 **NO-SHIP**" if risk["decision"] == "NO-SHIP" else "✅ **SHIP**"
    lines = [
        "# CISO executive summary\n",
        f"**Decision: {banner}**  ·  Risk posture score: **{risk['score']}/100**\n",
        f"- Controls: **{n_pass} passed**, **{n_fail} failed**, {n_na} N/A",
        f"- Alarms raised: **{len(alarms)}** ({len(crit)} critical)",
    ]
    if crit:
        lines.append("\n**Critical issues blocking deploy:**")
        for a in crit:
            lines.append(f"- `{a['type']}` — {a['recommended_action']}")
    if n_fail:
        failed = [f["control_id"] for f in findings if f["status"] == "FAIL"]
        lines.append(f"\n**Failed controls requiring remediation:** {', '.join(failed)}")
    lines.append("\n_This posture is backed by timestamped, source-linked evidence — "
                 "not the model's opinion. Every PASS has a verifiable artifact._")
    return "\n".join(lines)


def render_packet(record: dict) -> dict:
    """Assemble all rendered sections from a persisted run record."""
    findings = record["findings"]
    risk = record.get("risk") or risk_score(findings)
    alarms = record.get("alarms", [])
    return {
        "risk": risk,
        "control_matrix_md": control_matrix_md(findings),
        "evidence_report_md": evidence_report_md(findings, record.get("timestamp")),
        "pr_diffs_md": pr_diffs_md(findings),
        "ciso_summary_md": ciso_summary_md(findings, risk, alarms),
    }
