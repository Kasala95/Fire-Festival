"""API: the hardened public paste path (in-memory scan, size/guardrail limits)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app
from policy_to_proof.tools.ingest import MAX_INPUT_BYTES

client = TestClient(app)


def test_paste_clean_terraform_scans():
    r = client.post("/api/scan", json={
        "terraform": 'resource "aws_db_instance" "db" { storage_encrypted = false }',
        "worker": "stub"})
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["decision"] == "NO-SHIP"
    assert "control_matrix_md" in body["packet"]


def test_paste_hardcoded_secret_halts():
    r = client.post("/api/scan", json={
        "terraform": 'password = "SuperSecretP@ssw0rd123"', "worker": "stub"})
    assert r.status_code == 200
    s = r.json()["summary"]
    assert s["halted"] is True
    assert any(a["type"] == "SECRET_EXPOSED" for a in s["alarms"])


def test_paste_oversize_rejected_413():
    r = client.post("/api/scan", json={
        "terraform": "x" * (MAX_INPUT_BYTES + 1), "worker": "stub"})
    assert r.status_code == 413


def test_allowlist_target_still_works():
    r = client.post("/api/scan", json={"target": "full_demo", "worker": "stub"})
    assert r.status_code == 200


def test_unknown_target_rejected():
    r = client.post("/api/scan", json={"target": "/etc/passwd", "worker": "stub"})
    assert r.status_code == 400


def test_run_id_is_server_generated_not_client_controlled():
    # a client-supplied run_id must be ignored (no overwriting other runs).
    r = client.post("/api/scan", json={
        "target": "full_demo", "worker": "stub", "run_id": "attacker-owned"})
    assert r.status_code == 200
    assert r.json()["summary"]["run_id"].startswith("web-")


def test_xss_payload_in_paste_does_not_crash_server():
    # snippet echoes the line; client sanitizes on render. Server must stay 200.
    r = client.post("/api/scan", json={
        "terraform": 'kms_key_id = "<img src=x onerror=alert(1)>"', "worker": "stub"})
    assert r.status_code == 200
