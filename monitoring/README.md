# Monitoring — Prometheus + Grafana

Live, visual observability for the harness. The API exposes Prometheus metrics at
`/metrics`; Prometheus scrapes them; Grafana charts them on a pre-built dashboard.

## Run it

```bash
# 1. start the harness API on the host (separate terminal, from repo root)
.venv/bin/uvicorn api.main:app --port 8000

# 2. start Prometheus + Grafana
cd monitoring && docker compose up

# 3. open the dashboard — no login (anonymous admin is enabled for the demo)
open http://localhost:3000/d/policy-to-proof
```

Run a few scans in the web UI (http://localhost:8000) and the charts fill in
within ~5s (the scrape interval).

## What you see
- **Last risk score** (gauge, red < 60 < orange < 80 < green)
- **Total runs**, **runs halted**, **p95 run duration**, **tokens consumed**
- **Runs by decision** (SHIP vs NO-SHIP)
- **Alarms by type** (SECRET_EXPOSED, CONTROL_FAILED, LIMIT_EXCEEDED, …)
- **Control results by status** (PASS / FAIL / N_A)

## Pieces
- `prometheus/prometheus.yml` — scrapes `host.docker.internal:8000/metrics` every 5s.
- `grafana/provisioning/` — auto-wires the Prometheus datasource and loads the dashboard.
- `grafana/dashboards/policy-to-proof.json` — the dashboard.

If Docker isn't running, the raw metrics are still visible at
http://localhost:8000/metrics — Grafana is just the viewing layer on top.
