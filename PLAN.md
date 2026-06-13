# PLAN.md — Policy-to-Proof delivery plan

> Project roadmap and source-of-truth traceability for the Fired Festival
> 24-Hour Build Challenge. Maps the client requirement → architecture →
> implementation → demo. Authoritative requirement: **[REQUIREMENTS.pdf](REQUIREMENTS.pdf)**.
> Architecture detail + diagram: **[HARNESS.md](HARNESS.md)**.

## 1. Overview

**Policy-to-Proof** is an AI **harness** that proves a system is safe enough to ship.
Point it at infrastructure-as-code plus a vague requirement — _"make this SOC 2 ready
before deploy"_ — and it returns executable checks, timestamped evidence, suggested PR
fixes, and a CISO-ready verdict.

**Operating principle (the one invariant):** deterministic scanners perform every check;
the agent performs only judgment. The harness is **structurally incapable** of certifying
a control it cannot prove — even if the model returns `PASS`, the evidence gate downgrades
it to `FAIL` without a verifiable artifact. The judged artifact is the harness (the
constraints around the agent), not the model.

## 2. Client requirements (from REQUIREMENTS.pdf)

**Four pillars** — every required module hangs off the reference anatomy:

| Pillar | Delivers | Requirement |
|---|---|---|
| 1 · Loop | Checkpoints | Bounded scan loop; four ordered gates (parse → control → evidence → remediation) returning PASS/FAIL/N·A, persisted & replayable; behaviour changes on gate feedback; caps on turns/tokens/time. |
| 2 · Tools | Material handling | Deterministic scanners (checkov / tfsec / gitleaks style) as typed tools; clean corpus in, structured evidence out; swappable worker behind `evaluate()`. |
| 3 · Guardrails | Guardrails | Declared in `controls.yaml` — input (strip injection, size-limit), action (read-only, allow-list, never auto-apply), output (no PASS without evidence; redact secrets) + turn/token/spend limits. |
| 4 · Observability | Alarms | OTel span per check; named alarms `{type · context · severity · action}`, e.g. `SECRET_EXPOSED → halt`; tracks p95 latency, $/run, tool err%, eval pass-rate. |

**Control set — v1:** access logging · least privilege (no wildcard IAM) · secrets
management (no hardcoded creds; KMS) · encryption (at rest & in transit) · CI/CD (harness
as deploy gate).

**Rubric:**
- **MUST** — four separable modules; behaviour changes on gate feedback; guardrails
  declared; checkpoints pass/fail; alarms structured; runs on a real Terraform repo;
  HARNESS.md.
- **SHOULD** — swappable worker; checkpoint replay; human-in-the-loop on unmapped /
  missing-evidence / low-confidence.
- **BONUS** — swap a second worker live to prove portability.

## 3. Architecture

One Python package, one module per pillar, with the swappable engine wrapped inside.
See the **Mermaid diagram and step trace in [HARNESS.md](HARNESS.md)** for the full flow.

```
requirement → guardrail IN (strip / validate / redact secrets)
  → parse_gate → control_gate (scanners) → evidence_gate (provenance) → remediation_gate
  → guardrail OUT (no unproven PASS) → observability (span per step)
  → risk score | control matrix | evidence packet | PR diffs | CISO verdict
```

| Pillar | Module |
|---|---|
| 🔁 Loop | `policy_to_proof/loop/` — `orchestrator.py`, `checkpoints.py` |
| 🛠️ Tools | `policy_to_proof/tools/` — `ingest.py`, `scan_terraform.py`, `scan_secrets.py`, `registry.py`, `evidence.py` |
| 🛡️ Guardrails | `policy_to_proof/guardrails/` — `guardrails.py`, `redaction.py`, declared in `policy_to_proof/controls.yaml` |
| 📊 Observability | `policy_to_proof/observability/` — `tracer.py`, `alarms.py`, `store.py` |
| ⚙️ Engine (swappable) | `policy_to_proof/worker/` — `interface.py`, `claude_worker.py`, `stub_worker.py` |

## 4. Requirement → implementation traceability

| Requirement (PDF) | Pillar / module | Where | Status |
|---|---|---|---|
| Four ordered gates, PASS/FAIL/N·A | Loop | `loop/checkpoints.py` (`parse_gate`, `control_gate`, `evidence_gate`, `remediation_gate`) | ✅ Done |
| Behaviour changes on gate feedback | Loop | `evidence_gate` downgrades PASS→FAIL; unmapped → escalate; low-confidence → HITL (`loop/orchestrator.py`) | ✅ Done |
| Persisted & replayable checkpoints | Loop + Obs | `observability/store.py`; `Harness.replay(run_id, from_gate=…)` in `loop/orchestrator.py`; `runs/<id>.json` | ✅ Done |
| Bounded loop / caps | Loop | `MAX_CONTROLS_PER_RUN=25` (`loop/orchestrator.py`); token/time tracked | ⚠️ Partial (see §7) |
| Deterministic scanners as typed tools | Tools | `tools/registry.py` registry; `scan_terraform.py`, `scan_secrets.py` | ✅ Done |
| Clean corpus in, structured evidence out | Tools | `tools/ingest.py` → `ScanCorpus`; `tools/evidence.py` renders packet | ✅ Done |
| v1 controls: access logging, least privilege, secrets, encryption, CI/CD | Tools | scanners registered for AC-LOG, IAM-LP, SEC-MGMT, ENC, CICD | ✅ Done |
| Risk score / matrix / evidence / PR diffs / CISO verdict | Tools | `tools/evidence.py` | ✅ Done |
| Guardrails declared (input / action / output) | Guardrails | `policy_to_proof/controls.yaml` + `guardrails/guardrails.py` | ✅ Done |
| Redact secrets before agent/logs | Guardrails | `guardrails/redaction.py`, applied in `tools/ingest.py` | ✅ Done |
| No PASS without evidence | Guardrails + Loop | `guardrails.py` + `evidence_gate` | ✅ Done |
| Swappable worker behind `evaluate()` | Engine | `worker/interface.py` Protocol; `get_worker("claude"\|"stub"\|"auto")` | ✅ Done |
| OTel span per check | Observability | `observability/tracer.py` (OTel-shaped shim) | ✅ Done |
| Structured named alarms | Observability | `observability/alarms.py` `CATALOG` | ✅ Done |
| `SECRET_EXPOSED → halt` | Observability + Loop | `alarms.must_halt` halts run in `orchestrator.py` | ✅ Done |
| Reliability signals (p95, $/run, err%, pass-rate) | Observability | `tracer.metrics()` | ✅ Done (stub reports 0 tokens — §7) |
| Runs on a real Terraform repo | Delivery | `policy_to_proof/examples/halt_demo`, `…/full_demo` | ✅ Done |
| HARNESS.md | Delivery | [HARNESS.md](HARNESS.md) | ✅ Done |

## 5. Rubric coverage

**MUST**
- [x] Four separable modules — `loop/` · `tools/` · `guardrails/` · `observability/`
- [x] Behaviour changes on gate feedback — `evidence_gate` downgrade, escalation, HITL
- [x] Guardrails declared — `policy_to_proof/controls.yaml`
- [x] Checkpoints pass/fail — `loop/checkpoints.py`
- [x] Alarms structured — `observability/alarms.py`
- [x] Runs on a real Terraform repo — `policy_to_proof/examples/*`
- [x] HARNESS.md — present

**SHOULD**
- [x] Swappable worker — `worker/` Protocol + `get_worker()`
- [x] Checkpoint replay — `store.py` + `Harness.replay(..., from_gate=…)`
- [x] HITL on unmapped / missing-evidence / low-confidence — `orchestrator.py`

**BONUS**
- [x] Swap a second worker live — stub ↔ Claude via `--worker` / UI sidebar, zero harness change

## 6. How to run / 5-minute demo script

```bash
# setup
python -m venv .venv && .venv/bin/pip install -r requirements.txt

# 1. clean-ish posture, deterministic engine — exit 0 SHIP / 1 NO-SHIP / 2 escalate
.venv/bin/python run_cli.py --target policy_to_proof/examples/full_demo --worker stub

# 2. live halt — hardcoded secret trips SECRET_EXPOSED before any PASS is issued
.venv/bin/python run_cli.py --target policy_to_proof/examples/halt_demo --worker stub

# 3. checkpoint replay — reproduce a gate from disk without re-running prior stages
.venv/bin/python run_cli.py --replay evidence_gate --run-id <run_id>

# 4. portability — swap the engine, same harness (set ANTHROPIC_API_KEY first)
.venv/bin/python run_cli.py --target policy_to_proof/examples/full_demo --worker claude

# UI for the recorded walkthrough
.venv/bin/streamlit run app.py
```

**Narrative:** full_demo → risk score + control matrix + PR diffs + CISO verdict →
halt_demo halts on `SECRET_EXPOSED` → replay a checkpoint → swap stub→Claude to prove the
model is a commodity the harness invokes. Deploy via `render.yaml` / `Procfile`
(`ANTHROPIC_API_KEY` set in the platform dashboard; falls back to stub if absent).

## 7. Roadmap / known limitations (hardening beyond the rubric)

- [ ] **Remediation lint** — `remediation_gate` checks a fix exists but does not lint the
  diff; the PDF specifies "diff+lint". Add HCL/`terraform fmt`-style validation of the
  proposed diff before it passes.
- [ ] **Enforce token/time caps** — tokens and latency are tracked in `tracer.py` but only
  a control-count cap is enforced. Add `max_tokens_per_run` / wall-clock deadline to
  `controls.yaml` + `orchestrator.py` and halt on breach.
- [ ] **Automated tests** — no pytest suite (rubric doesn't require it). Add unit tests per
  scanner + a golden-record test over `examples/*` to lock the evidence packet.
- [ ] **Observability signals under stub** — `StubWorker` reports 0 tokens, so `$/run` and
  p95 read ~0 on offline runs. Emit synthetic per-call costs (or note "stub" in metrics) so
  the dashboard is non-empty during the deterministic demo.

---

_The model is a commodity invoked by the harness; the harness is the durable engineering —
the point at which trust is established: the moment before deployment._
