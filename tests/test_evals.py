import json
from pathlib import Path

import pytest

from app.agents.graph import SupportTriageGraph
from app.models.tickets import Ticket, TicketCategory, TicketCreate, TicketPriority
from app.services.knowledge_base import SupportKnowledgeBase
from app.services.llm import MockSupportTriageModel

GOLDEN_TICKETS_PATH = Path(__file__).resolve().parents[1] / "evals" / "golden_tickets.json"


@pytest.fixture
def graph() -> SupportTriageGraph:
    return SupportTriageGraph(SupportKnowledgeBase(), MockSupportTriageModel())


def _golden_cases() -> list[dict]:
    return json.loads(GOLDEN_TICKETS_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", _golden_cases(), ids=lambda case: case["name"])
def test_golden_ticket_eval(case: dict, graph: SupportTriageGraph) -> None:
    ticket = Ticket(**TicketCreate(**case["ticket"]).model_dump())
    report = graph.run(ticket, trace_id=f"eval-{case['name']}")

    expected = case["expected"]
    assert report.category == TicketCategory(expected["category"])
    assert report.priority == TicketPriority(expected["priority"])
    assert report.escalate is expected["escalate"]
    if expected["risk_review"]:
        assert "risk_review" in report.workflow_path
    else:
        assert "risk_review" not in report.workflow_path
