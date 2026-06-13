"""Policy-to-Proof — an AI harness that turns vague compliance requirements into
executable checks, timestamped evidence, and a remediation plan.

Four pillars (each a distinct module, separate from the worker):
  - guardrails:  declared rules, enforced around the agent
  - checkpoints: pass/fail gates with persisted, replayable results
  - materials:   ingest -> normalized corpus; redaction; evidence packet
  - alarms:      structured {type, context, severity, recommended_action}

The worker (agent) lives *inside* the harness behind a fixed interface.
"""
__version__ = "1.0.0"
