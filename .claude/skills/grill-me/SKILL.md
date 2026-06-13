---
name: grill-me
description: Adversarial pre-build interrogation. Before writing code, grill the user with pointed questions to surface hidden assumptions, edge cases, failure modes, scope creep, and missing requirements. Use when starting a feature or layer, when a plan feels under-specified, or when the user says "grill me". Do NOT write code until the questions are answered.
---

# Grill Me

Purpose: catch the expensive mistakes *before* any code exists, by attacking the plan with hard questions.

When invoked:
1. Restate the goal in one sentence so we agree on the target.
2. Ask 5–12 sharp questions, grouped under these headings (skip a heading only if truly N/A):
   - **Requirements & scope** — what's explicitly in, what's out, what's assumed?
   - **Edge cases & inputs** — empty, huge, malformed, concurrent, duplicate, hostile inputs?
   - **Failure modes** — what happens when a dependency / timeout / partial-write fails? Rollback?
   - **Data & migrations** — backward compatible? reversible? what about existing rows?
   - **Security & secrets** — authz, injection, secret handling, blast radius (ties to /trail-of-bits-security).
   - **Interfaces & contracts** — API shape, error codes, idempotency, versioning.
   - **Testing & done** — how do we *prove* it works? What's the acceptance bar?
3. Flag the single riskiest assumption explicitly: "If I had to bet on what breaks this, it's ___."
4. STOP and wait for answers. Do not start building until the user responds.

Rules:
- One question per line, numbered. No essays.
- Prefer questions whose answer changes the design, not trivia.
- If the user can't answer one, log it as an open risk to revisit — don't block forever.
