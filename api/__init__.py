"""FastAPI layer for Policy-to-Proof.

Exposes the harness over HTTP: trigger a scan, list/read run history, fetch the
rendered evidence packet, replay a checkpoint, and serve Prometheus metrics.
The web dashboard (web/) is served from here too.
"""
