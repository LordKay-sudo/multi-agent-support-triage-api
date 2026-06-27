from collections.abc import Sequence

from fastapi.testclient import TestClient
from langchain_core.messages import BaseMessage

from app.dependencies import get_triage_graph
from app.main import app
from app.services.llm import MockSupportTriageModel


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


def test_trace_id_matches_request_id_header() -> None:
    client = TestClient(app)
    ticket_id = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": "cust_trace",
            "subject": "Billing charge question",
            "description": "Question about a renewal charge on this month's invoice.",
        },
    ).json()["id"]

    request_id = "client-trace-123"
    response = client.post(
        f"/api/v1/tickets/{ticket_id}/triage",
        headers={"x-request-id": request_id},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == request_id
    assert response.json()["report"]["trace_id"] == request_id


def test_triage_failure_marks_ticket_failed() -> None:
    class FailingTriageModel(MockSupportTriageModel):
        def invoke(self, messages: Sequence[BaseMessage]) -> str:
            raise RuntimeError("draft generation failed")

    from app.agents.graph import SupportTriageGraph
    from app.core.config import get_settings
    from app.services.knowledge_base import SupportKnowledgeBase
    from app.services.tracing import TriageTracer

    failing_graph = SupportTriageGraph(
        SupportKnowledgeBase(),
        FailingTriageModel(),
        tracer=TriageTracer(get_settings()),
    )
    app.dependency_overrides[get_triage_graph] = lambda: failing_graph
    try:
        client = TestClient(app)
        ticket_id = client.post(
            "/api/v1/tickets",
            json={
                "customer_id": "cust_fail",
                "subject": "Billing charge question",
                "description": "Question about a renewal charge on this month's invoice.",
            },
        ).json()["id"]

        response = client.post(f"/api/v1/tickets/{ticket_id}/triage")

        assert response.status_code == 502
        assert response.json()["detail"]["trace_id"]
        ticket = client.get(f"/api/v1/tickets/{ticket_id}").json()
        assert ticket["status"] == "failed"
        assert ticket["failure_reason"]
    finally:
        app.dependency_overrides.clear()


def test_get_missing_ticket_returns_404() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/tickets/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
