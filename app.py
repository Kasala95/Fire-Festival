"""Policy-to-Proof — Streamlit UI.

Upload a Terraform file -> run the harness -> watch checkpoints fire -> read the
evidence packet. Built to drive the 5-minute demo:
  1. upload a real .tf (planted secret + wildcard IAM)
  2. SECRET_EXPOSED halts the run, live
  3. evidence packet: risk score, control matrix, timestamped evidence, PR diffs
  4. HITL escalation on an unmapped requirement
  5. swap the worker and re-run to prove portability
"""
from __future__ import annotations

import os
import tempfile

import streamlit as st

from policy_to_proof.loop.orchestrator import Harness
from policy_to_proof.worker import get_worker
from policy_to_proof.tools import evidence as ev

st.set_page_config(page_title="Policy-to-Proof", page_icon="🛡️", layout="wide")
st.title("🛡️ Policy-to-Proof")
st.caption("Vague compliance requirement → executable checks, timestamped evidence, remediation. "
           "Deterministic tools do the checking; the agent only does judgment.")

with st.sidebar:
    st.header("Run config")
    worker_choice = st.radio("Worker engine (swappable — zero harness changes)",
                             ["stub", "claude", "auto"], index=0)
    if worker_choice in ("claude", "auto") and not os.environ.get("ANTHROPIC_API_KEY"):
        st.warning("ANTHROPIC_API_KEY not set — 'auto' will fall back to the stub.")
    requirement = st.text_area("Compliance requirement",
                               "make this app SOC 2 ready before deployment")
    st.markdown("---")
    st.markdown("**Four pillars** · 🔁 Loop · 🛠️ Tools · 🛡️ Guardrails · 📊 Observability")

uploaded = st.file_uploader("Upload a Terraform file", type=["tf", "hcl"])
use_example = st.checkbox("Use the bundled demo (planted secret + wildcard IAM)", value=True)

if st.button("Run harness", type="primary"):
    if use_example:
        target = os.path.join(os.path.dirname(__file__), "policy_to_proof", "examples")
    elif uploaded:
        tmp = tempfile.mkdtemp()
        target = os.path.join(tmp, uploaded.name)
        with open(target, "wb") as fh:
            fh.write(uploaded.getbuffer())
    else:
        st.error("Upload a file or check 'Use the bundled demo'.")
        st.stop()

    worker = get_worker(worker_choice)
    harness = Harness(worker=worker)
    with st.spinner(f"Running checkpoints with engine: {worker.name} …"):
        record = harness.run(target, requirement, run_id="ui-run")

    # --- live checkpoint feed
    st.subheader("Checkpoints")
    for cp in record["checkpoints"]:
        icon = {"PASS": "✅", "FAIL": "❌", "N_A": "➖", "ESCALATE": "⚠️"}.get(cp["status"], "?")
        st.write(f"{icon} **{cp['name']}** — {cp['status']}  · _{cp['criteria']}_")

    if record["halted"]:
        st.error("🚨 Run HALTED by a critical alarm (SECRET_EXPOSED). "
                 "No certification possible until the secret is rotated and removed.")

    if record.get("escalations"):
        st.warning("⚠️ Human-in-the-loop escalation required:")
        for e in record["escalations"]:
            st.write(f"- {e}")

    packet = ev.render_packet(record)

    # --- risk + decision
    risk = packet["risk"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Risk posture", f"{risk['score']}/100")
    c2.metric("Decision", risk["decision"])
    c3.metric("Engine", worker.name)

    st.markdown(packet["ciso_summary_md"])

    st.subheader("Control matrix")
    st.markdown(packet["control_matrix_md"])

    if record["alarms"]:
        st.subheader("Alarms")
        for a in record["alarms"]:
            st.write(f"- **[{a['severity'].upper()}] {a['type']}** — {a['recommended_action']}  "
                     f"`{a['context']}`")

    with st.expander("Evidence report (timestamped, source-linked)"):
        st.markdown(packet["evidence_report_md"])
    with st.expander("Suggested remediation (PR diffs)"):
        st.markdown(packet["pr_diffs_md"])
    with st.expander("Observability — spans & metrics"):
        st.json(record["metrics"])
        st.json(record["spans"])

    st.caption(f"Run persisted to runs/{record['run_id']}.json — any checkpoint is replayable.")
