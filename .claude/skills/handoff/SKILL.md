---
name: handoff
description: Produce a handoff document so another session or engineer can pick up exactly where this one left off. Captures what's done, current state, next steps, key files, decisions, gotchas, and how to run/test. Use at the end of a work session, before a context reset, or when the user says "handoff".
---

# Handoff

Goal: a cold reader (or a fresh session) can continue with zero extra context.

Write a `HANDOFF.md` (or update the existing one) with these sections:
1. **Goal** — what we're ultimately building, in one or two sentences.
2. **Status now** — what's done and working, what's in progress. Be honest about half-finished bits.
3. **Next steps** — the ordered TODO list to resume. Most important first.
4. **Key files** — the files that matter, each with a one-line "why it matters" (use clickable paths).
5. **Decisions & why** — choices made and the reasoning, so they aren't re-litigated.
6. **Gotchas / landmines** — anything surprising, fragile, or easy to break.
7. **How to run & test** — exact commands to start the app and verify it works.
8. **Open questions** — unresolved things needing a human decision.

Rules:
- Link real paths and commands; no vague "the config file".
- State the current git branch and whether work is committed / pushed.
- Keep it scannable — headings + bullets, not prose.
