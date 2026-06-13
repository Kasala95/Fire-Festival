"use strict";

const $ = (id) => document.getElementById(id);
const md = (text) => (window.marked ? window.marked.parse(text || "") : `<pre>${text || ""}</pre>`);

async function getJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ---- examples dropdown ----------------------------------------------------
let EXAMPLES = [];
async function loadExamples() {
  EXAMPLES = await getJSON("/api/examples");
  const sel = $("target");
  sel.innerHTML = EXAMPLES.map((e) => `<option value="${e.id}">${e.id}</option>`).join("");
  sel.onchange = showBlurb;
  showBlurb();
}
function showBlurb() {
  const e = EXAMPLES.find((x) => x.id === $("target").value);
  $("blurb").textContent = e ? e.blurb : "";
}

// ---- run history ----------------------------------------------------------
function fmtTime(epoch) {
  if (!epoch) return "—";
  return new Date(epoch * 1000).toLocaleString();
}
async function loadHistory() {
  const runs = await getJSON("/api/runs");
  const tbody = document.querySelector("#history tbody");
  if (!runs.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="muted">No runs yet.</td></tr>`;
    return;
  }
  tbody.innerHTML = runs
    .map((r) => {
      const cls = r.decision === "SHIP" ? "ship" : "noship";
      return `<tr data-id="${r.run_id}">
        <td>${fmtTime(r.created_at)}</td>
        <td>${r.target ? r.target.split("/").pop() : "—"}</td>
        <td>${r.worker || "—"}</td>
        <td><span class="pill ${cls}">${r.decision || "—"}</span></td>
        <td>${r.risk_score ?? "—"}</td>
      </tr>`;
    })
    .join("");
  tbody.querySelectorAll("tr[data-id]").forEach((tr) => {
    tr.onclick = () => openRun(tr.dataset.id);
  });
}

// ---- render a result (from scan or history) -------------------------------
function renderResult(data) {
  const { summary, packet } = data;
  const decision = summary.decision || "—";
  const ship = decision === "SHIP";

  const verdict = $("verdict");
  verdict.classList.remove("hidden", "ship", "noship");
  verdict.classList.add(ship ? "ship" : "noship");
  $("verdict-decision").textContent = ship ? "✅ SHIP" : "🚫 NO-SHIP";
  const score = packet.risk ? packet.risk.score : "—";
  $("verdict-risk").textContent = `Risk ${score}/100` + (summary.halted ? " · HALTED" : "");

  $("result-empty").classList.add("hidden");
  $("result").classList.remove("hidden");

  $("tab-summary").innerHTML = md(packet.ciso_summary_md);
  $("tab-matrix").innerHTML = md(packet.control_matrix_md);
  $("tab-evidence").innerHTML = md(packet.evidence_report_md);
  $("tab-diffs").innerHTML = md(packet.pr_diffs_md || "_No remediation needed._");

  const alarms = summary.alarms || [];
  $("tab-alarms").innerHTML = alarms.length
    ? `<ul class="alarms">${alarms
        .map((a) => `<li class="sev-${a.severity}"><strong>${a.type}</strong>
           <span class="sev">${a.severity}</span><br/>${a.recommended_action}</li>`)
        .join("")}</ul>`
    : `<p class="muted">No alarms.</p>`;

  showTab("summary");
}

function showTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  ["summary", "matrix", "alarms", "evidence", "diffs"].forEach((n) => {
    $(`tab-${n}`).classList.toggle("hidden", n !== name);
  });
}

async function openRun(runId) {
  $("scan-status").textContent = "";
  try {
    renderResult(await getJSON(`/api/runs/${runId}/packet`));
  } catch (e) {
    $("scan-status").textContent = `Error: ${e.message}`;
  }
}

// ---- run a new scan -------------------------------------------------------
async function runScan() {
  const btn = $("run");
  btn.disabled = true;
  $("scan-status").textContent = "Running gates…";
  try {
    const data = await getJSON("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target: $("target").value,
        requirement: $("requirement").value,
        worker: $("worker").value,
      }),
    });
    renderResult(data);
    $("scan-status").textContent = `Done — run ${data.summary.run_id}`;
    await loadHistory();
  } catch (e) {
    $("scan-status").textContent = `Error: ${e.message}`;
  } finally {
    btn.disabled = false;
  }
}

// ---- wire up --------------------------------------------------------------
document.querySelectorAll(".tab").forEach((t) => (t.onclick = () => showTab(t.dataset.tab)));
$("run").onclick = runScan;
loadExamples();
loadHistory();
