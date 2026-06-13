---
name: trail-of-bits-security
description: Rigorous defensive security review in the style of Trail of Bits. Threat-model the change, hunt the standard vulnerability classes, and report findings with severity, exact location, exploit scenario, and a concrete fix. Use before merging security-sensitive layers (auth, input handling, IaC, secrets, crypto) or when the user says "trail of bits" or "security review". Defensive only.
---

# Trail of Bits Security Review

Mindset: assume the input is hostile and the attacker is patient. Be concrete — no generic "validate inputs" advice without naming the input, the file, and the attack.

Steps:
1. **Scope & threat model** — what changed, which data / trust boundaries it touches, who the attacker is, and what they want.
2. **Hunt these classes** (check each; write "n/a" if it genuinely doesn't apply):
   - Injection — SQL, command, template, HCL/YAML, prompt injection
   - AuthN / AuthZ — missing checks, IDOR, privilege escalation, wildcard permissions
   - Secrets — hardcoded creds, secrets in logs/errors, weak redaction
   - Crypto — at rest & in transit, weak/missing encryption, bad randomness
   - Input handling — size limits, parsing, deserialization, path traversal
   - Supply chain — dependency pinning, untrusted packages, CI/CD trust
   - Error handling & DoS — unbounded loops, resource exhaustion, info leak in errors
   - State & concurrency — TOCTOU, race conditions, partial writes
3. **Report each finding** as:
   - `[SEVERITY: critical | high | medium | low]` short title
   - Location: `file:line`
   - Why it's exploitable: a 1–2 sentence attack scenario
   - Fix: the concrete change to make
4. **Verdict**: ship / fix-first, with a count by severity. Never say "looks fine" without having actually walked each class above.

Boundary: defensive review only — find and fix weaknesses. Never write working exploit or attack tooling.
