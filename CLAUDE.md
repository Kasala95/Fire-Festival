# CLAUDE.md — Policy-to-Proof working agreement

This file is read at the start of every session. It defines **how we build in this repo**.

## Project
Policy-to-Proof: an AI **harness** that proves infrastructure-as-code is safe to ship.
- Source of truth: [REQUIREMENTS.pdf](REQUIREMENTS.pdf)
- Architecture + diagram: [HARNESS.md](HARNESS.md)
- Delivery roadmap: [PLAN.md](PLAN.md)

## How I must communicate (important)
- Explain every tool, concept, and command in **plain, simple English**, in detail.
- Define jargon the first time it appears; assume no prior knowledge of the tool.
- Use the shape "what it is → why it matters → what happens when you run it."
- This holds for everything — unless `/caveman` mode is invoked, which makes me terse.

## How we build: layers, one PR per layer
Build and ship in **layers**, bottom-up. Each layer is its **own pull request**, in this order:
1. **DB migration** — schema / data changes first (the foundation).
2. **Service layer** — business logic built on top of the schema.
3. **API layer** — endpoints that expose the service.
4. **Front end** — the UI that calls the API.

Rules:
- One layer = one PR. Never mix two layers in a single PR.
- Build bottom-up: a layer is only added after the layer below it is in place.
- Keep each PR small, reviewable, and understandable on its own.

## Stacked PRs with Graphite
We use **Graphite** (`gt`, https://graphite.dev) to **stack** these PRs: each layer's PR sits
on top of the one below it, so I can keep building upward without waiting for the lower PR
to be merged first.
- Each layer is a branch stacked on the previous: `db → service → api → frontend`.
- `gt create` — make the next stacked branch + commit.
- `gt submit` — push the whole stack up as a set of linked PRs.
- `gt sync` / `gt restack` — keep the stack consistent after a lower PR changes or merges.
- If `gt` isn't installed, fall back to plain stacked git branches and say so explicitly.

## Skills (reusable workflows) — invoke with /<name>
- **/deploy-agent** — pick where/how to host an agent (5 considerations → 4 questions → platform), then deploy.
- **/grill-me** — interrogate the plan with hard questions *before* writing code.
- **/trail-of-bits-security** — rigorous defensive security review of a change.
- **/karpathy-guidelines** — write / review code for simplicity and readability.
- **/caveman** — terse, token-efficient output (say more with less).
- **/handoff** — write a HANDOFF.md so another session can continue cleanly.
