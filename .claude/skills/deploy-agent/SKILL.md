---
name: deploy-agent
description: Decide how and where to ship an AI agent to production, then deploy it. Walks the deployment framework from the Fire Festival lecture — the 5 things to remember (agents are not APIs), the 4 driving questions, and the AWS / Azure / Railway-Render-Fly trade-offs — to a concrete platform pick, then runs the actual deploy (free Render for Fire Festival). Use when deploying/hosting an agent, choosing a platform, or when the user says "deploy", "ship it", or "where do I host this".
---

# Deploy Agent — from "it works locally" to "it's live"

Source material: the Fire Festival "Deploying AI Agents in Production" deck + lecture transcripts
([Presentation 3](https://otter.ai/u/JP9amriM8_53JBQuUW3WKR4AfDM), [Presentation 1](https://otter.ai/u/o_HbYALLzXeQE3FWR9yi55fMsxg)).

Core idea: **agents are not APIs.** A REST endpoint is fast, stateless, request-response. An agent is a long-running state machine that calls tools, holds memory, spawns sub-agents, and burns unpredictable tokens. You cannot pick a host the way you'd pick one for a CRUD API. Work the framework below before you deploy.

## Step 1 — The 5 things to remember (agents are not APIs)

Walk each one for *this* agent. Don't skip; each one rules platforms in or out.

1. **Execution time** — how long is one full job, from task initiated → completed → reviewed → accepted? For a multi-agent system it's until the *whole* job across all agents is done. 30s? 5 min? 30 min? This is the single biggest input. (Lecture example: a SQL customer-support bot ran ~4 min end to end → the host had to tolerate multi-minute runs, which kills 15-min-capped serverless on bigger jobs.)
2. **State management** — three kinds, name which you need:
   - *Working memory* — the in-run state object (e.g. a LangGraph state dict): every tool call / MCP result / action logged during one execution.
   - *Short-term memory* — preserved across short-lived sessions (e.g. Claude Code's memory index updating as you work — last touch on a repo gets pulled back into context).
   - *Long-term memory* — durable store: a `CLAUDE.md`, a Redis cache, a DB, the "factory memo" every agent must read. Preferences and how-work-is-done.
3. **Cold starts** — cloud abstractions take time to spin up. Lambda-style function ≈ 200ms–1.2s; a container (ECS) ≈ ~30s; managed runtimes (Bedrock AgentCore / Azure durable functions) ≈ near-zero. Ask: sporadic or continuous requests? Must it be on at all times, or only when needed?
4. **Concurrency** — the agent leaves its sandbox to call tools. With 1000 users running the same agent, how many times does each tool get called? Map expected tool-call volume against capacity, or a shared tool gets hammered.
5. **Cost & predictability** — LLMs are black boxes; input tokens hide. Dead MCP JSON can waste ~40k tokens per call. Idle-but-running cloud agents still bill. Before prod: cut dead tokens, cache prompts, route the right model to the right complexity (don't use a top model on a trivial task).

## Step 2 — The 4 questions that pick the platform

1. **How long do agent runs typically take?** → decides if serverless timeouts are viable.
2. **Is traffic steady, bursty, or sporadic?** → drives always-on vs. pay-per-use.
3. **Do you need WebSockets or streaming?** → agents need transparency (watch deep-research stream its branches); streaming need rules out many serverless-edge options.
4. **How much ops overhead can the team absorb?** → small startup ≠ a team with its own DevOps already priced into Azure. Separates managed PaaS from DIY infra.

## Step 3 — Pick the platform

**AWS** (max control, max complexity):
| Service | Best for | Exec limit | Cold start |
|---|---|---|---|
| Bedrock AgentCore | Fully managed runtime + observability/evals; **start here on AWS** | Managed | Near-zero |
| Lambda | Event-driven, short agents | 15 min | 200ms–1.2s |
| ECS Fargate | Long-running, always-on container | Unlimited | ~30s |
| EKS (Kubernetes) | Multi-agent, millions of users, spawn duplicate agents w/ session memory | Unlimited | ~60s |

**Azure** (Microsoft-stack enterprises): **durable functions** = a Lambda with *zero* cold start (start here on Azure); AKS ≈ EKS; AI Foundry Agent Service = managed runtime. Watch-out: Foundry observability is weak — you build your own evals, log everything yourself, pay for the Postgres. AWS observability (AgentCore/Strands) is better; good external tools: LangFuse-style viewers, Braintrust.

**Recommendation (lecture):** start with **AgentCore (AWS)** or **durable functions (Azure)** — ~$100/mo, affordable. Scale up to Fargate / Kubernetes only as you hit hundreds-of-thousands of users. GCP Cloud Run is a top-tier serverless-container alternative; Vertex AI Agent Builder adds Google-Search grounding.

**Simpler platforms (ship today):**
| Platform | Cold start | Exec | WebSockets | Setup | Cost |
|---|---|---|---|---|---|
| Render | 0ms paid / ~15–30s free | Unlimited | Yes | ~10 min | ~$5–25 |
| Railway | 0ms ($20 always-on) / ~15–30s ($5) | Unlimited | Yes | ~15 min | ~$20–40 |
| Fly.io | 0ms (paid) | Unlimited | Yes | ≤15 min | ~$20–35 |

**Defaults:**
- **Fire Festival → free Render account.** Enough to host the agent/harness so judges can hit it live. Accept the ~15-min idle spin-down on free tier.
- **Launching for real next week → $40/mo Railway.** One plan hosts the Postgres, the agent container, and (with Vercel for the front end) the whole stack.

## Step 4 — State before you scale

When you spawn a container per agent (the Kubernetes/factory pattern), each new agent must "put on its harness." **Harness = evals + memory + context + tools** (evals include the golden set; the agent itself is the brain/LLM over the tools). Every new cloud container needs its memory, evals, context, and any process state ported in. Before deploying, decide: when is a new container created, how long does it live, how long is the execution flow, what's the optimal shape. **Think about state before you launch**, especially with managed runtimes.

## Step 5 — Deploy (Render, Fire Festival path)

Plain-English, in order:

1. **Dockerize the agent locally first** (the deploy assumes a working local container).
2. **Install the Render CLI** — the command-line tool that talks to Render.
   - Mac: `brew install render`
   - PC/Windows: download from the Render website.
3. **Log in:** `render login` → opens the browser, connects your (free) account, mints a CLI token stored in your account.
4. **Generate the deploy manifest** (`render.yaml` — the "blueprint" file listing every service Render must stand up). From the project dir, use the Render skill: `npx render` and ask it to *"generate the blueprint to match what I've been running locally."* It reads your local Docker setup and writes the YAML.
5. **Inspect the generated `render.yaml` in your IDE before deploying** — check env vars are correct, check it's building the right services. Do not deploy blind.
6. **Deploy via the CLI.** ~15 min to go live. On free tier it spins the service down after ~15 min idle and back up on the next request (the cold start); a $5 plan makes that ~0s.

**Plugins vs. skills (why we use the official ones):** a *plugin* = a package of MCP tools (MCP JSON) **+** skills + tool connections; one install wires the whole integration into Claude Code / Codex / Cursor. A *skill* = reusable, progressively-disclosed instructions (only the ~200-char description sits in context until invoked). Railway, Render, and Fly each ship an official plugin; the `SKILL.md` is editable at project level for your naming/conventions.

**Security:** only use skills/plugins published by the company you're integrating (Railway, Render, Fly) — there have been vulnerabilities in random third-party skills. Vet unknown ones with NVIDIA's open-source skill inspector. (For a deeper pass, hand the change to `/trail-of-bits-security`.)

## Output of this skill

Don't just deploy. First produce a short verdict:
- The 5 considerations answered for *this* agent (one line each).
- The 4 questions answered.
- **Platform pick + why**, tied to those answers (not a generic "use X").
- Then the concrete deploy steps for the chosen platform.
