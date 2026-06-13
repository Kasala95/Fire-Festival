# HARNESS.md — Policy-to-Proof architecture & design

## What this is

Policy-to-Proof is an **AI harness**: the runtime scaffolding that wraps a raw
language model so it becomes a reliable, observable, tool-using agent for
compliance work. The agent (the "engine") lives _inside_ the harness. Everything
that makes it safe and useful — the loop, the tools, the guardrails, the
observability — is code wrapped around the model.

> The model is the engine. The harness is the car.

The judged artifact is the **harness**, not the agent. So the design optimizes for
a clean, demonstrable separation of concerns.

## The one invariant

**Deterministic tools do the checking. The agent only does judgment.**

The agent maps requirements → controls, interprets scanner output into findings,
and drafts remediation. It is **structurally incapable of marking a control PASS
without a verifiable artifact** — even if the model returns `PASS`, the
`evidence_gate` downgrades it to `FAIL` unless a deterministic scanner produced a
proof. Constraint-handling is invisible to the agent: it gets `control + corpus +
scan` and returns a `Finding`; the harness decides what is allowed, what passes,
and what trips an alarm.

## The four pillars (Fired Festival deck) and where they live

The deck defines four responsibilities present in every harness, wrapped around a
central loop. This repo is organized around exactly those pillars:

| Pillar | Module | Responsibility |
|---|---|---|
| 🔁 **Chat / Loop** | `policy_to_proof/loop/` | `orchestrator.py` drives the train of thought, one pass per control; `checkpoints.py` holds the gates that branch/stop the loop. |
| 🛠️ **Tools** | `policy_to_proof/tools/` | `ingest.py` reads material → `ScanCorpus`; `scan_*.py` are the deterministic checkers (checkov/tfsec/gitleaks-style); `registry.py` is the typed tool registry; `evidence.py` renders the egress packet. |
| 🛡️ **Guardrails** | `policy_to_proof/guardrails/` | `guardrails.py` enforces declared rules (no-unproven-PASS, scope-lock, read-only, confidence floor); `redaction.py` is the input guardrail that masks secrets before anything reaches the agent or logs. |
| 📊 **Observability** | `policy_to_proof/observability/` | `tracer.py` emits a span per model/tool call + the four reliability signals; `alarms.py` is the structured alarm bus; `store.py` persists runs for checkpoint replay. |
| ⚙️ _engine_ | `policy_to_proof/worker/` | The swappable agent behind a fixed `Worker` interface. Not a pillar — it's what the pillars wrap. |

### The agent loop (train of thought)

```
ingest material (TOOL, read-only)  ──► redact secrets (GUARDRAIL, input)
  │
  ├─ SECRET_EXPOSED? → ALARM (critical) → HALT          [Observability + Loop stop]
  │
parse_gate: requirement → controls (ENGINE judgment)    [Loop checkpoint]
  │   └─ no mapping → UNMAPPED_REQUIREMENT → escalate (HITL)
  │
for each in-scope control:                              [Loop body]
    run scanner            (TOOL — the checking)
    worker.evaluate(...)   (ENGINE — judgment only)
    enforce_finding(...)   (GUARDRAIL — no unproven PASS, confidence floor)
    evidence_gate(...)     (Loop checkpoint — the PASS authority)
    remediation_gate(...)  (Loop checkpoint — every FAIL has a fix)
    emit spans + alarms    (Observability)
  │
control_gate → finalize → risk score + decision → persist run  [Loop stop + Observability]
```

## Checkpoints (explicit pass/fail criteria, persisted & replayable)

| Gate | Criteria | On failure |
|---|---|---|
| `parse_gate` | requirement maps to ≥1 declared control | `ESCALATE` → `UNMAPPED_REQUIREMENT` alarm, human-in-the-loop |
| `control_gate` | every in-scope control resolves to PASS/FAIL/N_A | run marked incomplete |
| `evidence_gate` | every PASS has a verifiable artifact and zero violations | **downgrade PASS → FAIL**, `EVIDENCE_MISSING` alarm |
| `remediation_gate` | every FAIL has a non-empty remediation targeting the control | flagged for review |

Each `CheckpointResult` is written to `runs/<run_id>.json`. `Harness.replay(run_id,
from_gate=...)` loads a specific gate's result from disk without re-running prior
stages — satisfying the "replay from any checkpoint" requirement and the auditor
user story (reproduce any finding).

## Alarms (structured: `{type, context, severity, recommended_action}`)

Declared in `observability/alarms.py::CATALOG` so triage is deterministic:

| Type | Severity | Action | Halts? |
|---|---|---|---|
| `SECRET_EXPOSED` | critical | rotate credential, remove from source | **yes** |
| `EVIDENCE_MISSING` | high | cannot certify; escalate | no |
| `CONTROL_FAILED` | high | generate remediation PR | no |
| `INSECURE_DEFAULT` | medium | set the secure value explicitly | no |
| `UNMAPPED_REQUIREMENT` | medium | escalate to human (HITL) | no |
| `LOW_CONFIDENCE_FINDING` | low | route to human review | no |

The agent's behavior changes based on this feedback: a failed `evidence_gate`
forces a downgrade (never a PASS), an unmapped requirement halts and asks rather
than guessing, and a critical secret halts the whole run.

## Swappable engine (portability)

`worker/interface.py` defines a `Worker` Protocol with two methods:
`map_requirement` and `evaluate`. Two implementations ship:

- `ClaudeWorker` (default) — Anthropic API; key from `ANTHROPIC_API_KEY`, never hardcoded.
- `StubWorker` — deterministic, no network; the offline default and the live portability proof.

`get_worker("claude"|"stub"|"auto")` selects one. **The rest of the harness never
branches on which engine it got** — swapping models requires zero harness changes.
This is demonstrable live: run a control with the stub, then re-run with Claude.

## Material handling

`ingest_path` reads a Terraform file or directory (read-only) and produces a
`ScanCorpus`: normalized resources, a flattened config map, and the redacted file
text. The corpus shape is **format-agnostic** — a Kubernetes/YAML parser could feed
the same shape via a new `parse_*` with zero downstream changes. The
secret-redaction lane masks detected secrets _before_ the corpus is built, so
nothing unredacted reaches the agent or the logs. Egress (`evidence.py`) renders
the risk score, control matrix, timestamped/source-linked evidence report, PR
diffs, and CISO summary.

## Controls — v1 SOC 2 vertical slice

Declared in `controls.yaml` (guardrails are declared, not implicit): access
logging, least privilege, secrets management, encryption, and CI/CD gate. Five
controls done well, not all of SOC 2.

## Running & deploying

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt

# CLI gate — exit 0 = SHIP, 1 = NO-SHIP/halt, 2 = escalation
.venv/bin/python run_cli.py --target policy_to_proof/examples/full_demo --worker stub

# Web UI
.venv/bin/streamlit run app.py
```

Deploy: `render.yaml` (Render blueprint) or `Procfile` (Fly.io / Heroku-style).
Set `ANTHROPIC_API_KEY` in the platform dashboard to enable the Claude engine; the
harness falls back to the stub if it's absent.

## Mapping to the build-prompt's pillars

The build prompt named its pillars guardrails / checkpoints / material handling /
alarms. Those map cleanly onto the deck's four: **guardrails** → Guardrails;
**checkpoints** → Loop (gates) + Observability (persistence); **material handling**
→ Tools (ingest + egress); **alarms** → Observability. Both rubrics are satisfied
by the same code.
