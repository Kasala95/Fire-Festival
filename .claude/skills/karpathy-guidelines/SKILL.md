---
name: karpathy-guidelines
description: Write and review code by Andrej Karpathy's engineering principles — favor the simplest thing that works, readability over cleverness, small explicit functions, no premature abstraction, and code you can fully hold in your head. Use when writing new code or reviewing a diff for quality and simplicity, or when the user says "karpathy".
---

# Karpathy Guidelines

Apply these when writing or reviewing code:

1. **The best code is no code.** Before adding, ask if it's needed at all. Deleting beats adding.
2. **Keep it simple and dumb first.** Write the obvious version. Add cleverness only when a real, measured need forces it. No speculative generality.
3. **Readability beats cleverness.** Optimize for the next human reading it. Boring, explicit code wins.
4. **Small, single-purpose functions.** Each does one thing, short enough to hold in your head.
5. **Be explicit.** Clear names, obvious data flow, no magic. Make shapes / types / contracts visible.
6. **Assert your assumptions.** Add guards that fail loudly when reality differs from what you assumed (shapes, ranges, invariants).
7. **Avoid premature abstraction.** Don't build a framework for one use. Wait for the third repetition before generalizing.
8. **Match the surrounding code.** Consistency with the existing style beats personal preference.
9. **Tight feedback loops.** Make it runnable and testable early; verify each small step instead of one big leap.

When reviewing: call out the *smallest* change that makes the code simpler, clearer, or shorter — and say what to delete.
