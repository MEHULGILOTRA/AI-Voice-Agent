"""
API-level integration tests for outreach endpoints.
Uses the test_app fixture (FastAPI TestClient with mocked services).
"""
import pytest


def test_health_liveness(test_app):
    resp = test_app.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_scenarios(test_app):
    resp = test_app.get("/api/v1/outreach/scenarios")
    assert resp.status_code == 200
    scenarios = resp.json()["scenarios"]
    assert len(scenarios) == 5
    ids = [s["scenario_id"] for s in scenarios]
    assert "S001" in ids
    assert "S005" in ids


def test_run_scenario_s001(test_app):
    resp = test_app.post("/api/v1/outreach/scenario/S001/run")
    # Either completes or pauses for review
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["parent_id"] == "P001"


def test_run_scenario_s003_whatsapp(test_app):
    resp = test_app.post("/api/v1/outreach/scenario/S003/run")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("outreach_status") == "unreachable" or "whatsapp_sent" in data


def test_run_unknown_scenario(test_app):
    resp = test_app.post("/api/v1/outreach/scenario/S999/run")
    assert resp.status_code == 404


def test_list_parents(test_app):
    resp = test_app.get("/api/v1/outreach/parents")
    assert resp.status_code == 200
    data = resp.json()
    assert "parents" in data
    assert len(data["parents"]) > 0
