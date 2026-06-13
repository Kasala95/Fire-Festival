# Policy-to-Proof — Fire-Festival

> An AI **harness** that turns a vague compliance requirement — _"make this app
> SOC 2 ready before deployment"_ — into executable checks, timestamped evidence,
> and a remediation plan.

Point it at a real Terraform file and it returns a **risk score**, **failed
controls**, an **auto-generated evidence packet**, **suggested PR diffs**, and a
**CISO executive summary** — backed by verifiable artifacts, not the model's opinion.

Built for the [Fired Festival](https://fired-festival.com/harness) AI-first
engineering event. This project is judged on the **harness** (the constraints
around the agent), not the agent itself.

> 📄 **[`REQUIREMENTS.pdf`](REQUIREMENTS.pdf)** is the authoritative client
> requirement and single source of truth for this project.

---

## The one design principle

**Deterministic tools do the checking. The agent only does judgment.**

The agent maps requirements → controls, interprets findings, and drafts
remediation — but it is **structurally incapable of marking a control PASS
without a verifiable artifact**. Constraint-handling is invisible to the agent:
it receives `control + evidence` and returns a finding; the harness decides what
is allowed, what passes, and what trips an alarm.

---

## The four pillars (housed per the Fired Festival deck)

The Fired Festival "Building an AI Harness" deck defines four pillars wrapped
around a central agent loop — _"the model is the engine, the harness is the car."_
This repo is organized around exactly those pillars:

| Deck pillar | Module | What it does here |
|---|---|---|
| 🔁 **Chat / Loop** | [`loop/`](policy_to_proof/loop) | The orchestrator (train of thought) + checkpoint gates that branch/stop the loop |
| 🛠️ **Tools** | [`tools/`](policy_to_proof/tools) | Material ingest, deterministic scanners (the checking), evidence-packet rendering |
| 🛡️ **Guardrails** | [`guardrails/`](policy_to_proof/guardrails) | Declared rules: no unproven PASS, read-only target, secret redaction, scope-lock |
| 📊 **Observability** | [`observability/`](policy_to_proof/observability) | Structured spans + reliability metrics, alarms, persistence & checkpoint replay |
| ⚙️ _engine_ | [`worker/`](policy_to_proof/worker) | The swappable agent behind a fixed interface (Claude default, stub fallback) |

The agent loop, one pass per control:

```
build context (control + corpus)
  → call ENGINE (worker judgment)         [worker, wrapped by guardrails]
  → run TOOL (deterministic scanner)      [Pillar 2: tools]
  → apply GUARDRAILS (no unproven PASS)   [Pillar 3: guardrails]
  → run CHECKPOINTS (evidence/remediation gates)  [Pillar 1: stop/branch]
  → EMIT spans + ALARMS, persist          [Pillar 4: observability]
stop when all controls resolved OR a halting alarm (SECRET_EXPOSED) fires.
```

---

## Checkpoint gates (in order)

1. `parse_gate` — requirement maps to ≥1 control, else **escalate** (human-in-the-loop)
2. `control_gate` — each control resolves to PASS / FAIL / N_A
3. `evidence_gate` — **the PASS authority**: every PASS needs a verifiable artifact, else downgrade to FAIL
4. `remediation_gate` — each FAIL has a remediation diff that targets the failed control

Results persist to `runs/<run_id>.json` so any gate is **replayable** without
re-running prior stages.

## Alarm types (structured: `{type, context, severity, recommended_action}`)

`SECRET_EXPOSED` (critical → halt, flag rotation) · `EVIDENCE_MISSING` (high →
cannot certify, escalate) · `CONTROL_FAILED` (high → generate remediation PR) ·
`INSECURE_DEFAULT` (medium) · `UNMAPPED_REQUIREMENT` (medium → HITL) ·
`LOW_CONFIDENCE_FINDING` (low → human review).

## Controls — v1 SOC 2 vertical slice (declared in [`controls.yaml`](policy_to_proof/controls.yaml))

1. **Access logging** — CloudTrail, S3 access logging, VPC flow logs
2. **Least privilege** — IAM policies without wildcard `"*"` actions/resources
3. **Secrets management** — no hardcoded credentials; KMS references present
4. **Encryption** — at rest (S3/RDS/EBS) and in transit (TLS)
5. **CI/CD checks** — the harness itself as a deployment gate

---

## Run it

```bash
pip install -r requirements.txt

# CLI dry-run on the bundled example (works with no API key — uses the stub engine)
python run_cli.py --target policy_to_proof/examples --requirement "make this SOC 2 ready"

# Web UI
streamlit run app.py
```

Set `ANTHROPIC_API_KEY` to use the Claude engine; otherwise the harness falls
back to the deterministic stub worker (which also proves portability). The key is
read from the environment and **never hardcoded**.

## Swappable engine (portability)

```python
from policy_to_proof.loop.orchestrator import Harness
from policy_to_proof.worker import get_worker

Harness(worker=get_worker("claude")).run(...)   # Claude
Harness(worker=get_worker("stub")).run(...)      # deterministic stub — zero harness changes
```

---

See **[HARNESS.md](HARNESS.md)** for the architecture and design rationale.
