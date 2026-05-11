from fastapi.testclient import TestClient

from app.main import app


def test_create_and_run_ticket() -> None:
    client = TestClient(app)

    create_response = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": "cust_789",
            "subject": "Payments API error",
            "description": "The payments API returns an error and our checkout is blocked.",
            "channel": "chat",
        },
    )
    assert create_response.status_code == 201
    assert create_response.headers["x-request-id"]
    ticket_id = create_response.json()["id"]

    run_response = client.post(f"/api/v1/tickets/{ticket_id}/triage")

    assert run_response.status_code == 200
    body = run_response.json()
    assert body["status"] == "triaged"
    assert body["report"]["category"] == "technical"
    assert body["report"]["confidence"] > 0
    assert body["report"]["recommended_actions"]


def test_triage_is_idempotent_unless_forced() -> None:
    client = TestClient(app)
    ticket_id = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": "cust_999",
            "subject": "Billing charge question",
            "description": "Question about a renewal charge on this month's invoice.",
        },
    ).json()["id"]

    first_run = client.post(f"/api/v1/tickets/{ticket_id}/triage").json()
    second_run = client.post(f"/api/v1/tickets/{ticket_id}/triage").json()
    forced_run = client.post(f"/api/v1/tickets/{ticket_id}/triage?force=true").json()

    assert second_run["report"]["trace_id"] == first_run["report"]["trace_id"]
    assert forced_run["report"]["trace_id"] != first_run["report"]["trace_id"]


def test_get_missing_ticket_returns_404() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/tickets/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
