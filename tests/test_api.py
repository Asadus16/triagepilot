import os

os.environ.setdefault("SERVICE_API_KEY", "test-key")
os.environ.setdefault("TICKETS_DB", "data/test_tickets.db")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_rules_endpoint_lists_the_whole_catalog_with_no_key_needed():
    resp = client.get("/rules")
    assert resp.status_code == 200
    rule_ids = {r["rule_id"] for r in resp.json()}
    assert "E01" in rule_ids and "R01" in rule_ids
    assert len(rule_ids) == 15


def test_triage_rejects_a_missing_or_wrong_service_key():
    resp = client.post("/triage", json={"customer_name": "A", "customer_email": "a@example.com", "subject": "s", "message": "hello"})
    assert resp.status_code == 401
    resp = client.post(
        "/triage",
        json={"customer_name": "A", "customer_email": "a@example.com", "subject": "s", "message": "hello"},
        headers={"x-service-key": "wrong"},
    )
    assert resp.status_code == 401


def test_human_review_rejects_mismatched_ticket_id():
    resp = client.post(
        "/human/abc",
        json={"ticket_id": "def", "action": "approved"},
        headers={"x-service-key": "test-key"},
    )
    assert resp.status_code == 400


def test_overdue_needs_a_key_and_starts_empty_on_a_fresh_database():
    assert client.get("/overdue").status_code == 401
    resp = client.get("/overdue", headers={"x-service-key": "test-key"})
    assert resp.status_code == 200
    assert isinstance(resp.json()["overdue"], list)


def test_escalate_overdue_404s_for_an_unknown_ticket():
    resp = client.post("/escalate-overdue/does-not-exist", headers={"x-service-key": "test-key"})
    assert resp.status_code == 404
