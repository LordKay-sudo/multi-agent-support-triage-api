from app.agents.graph import SupportTriageGraph
from app.models.tickets import Ticket, TicketCategory, TicketCreate, TicketPriority
from app.services.knowledge_base import SupportKnowledgeBase
from app.services.llm import MockSupportChatModel


def test_graph_routes_high_risk_account_ticket_through_risk_review() -> None:
    ticket = Ticket(
        **TicketCreate(
            customer_id="cust_123",
            subject="Cannot access account before payroll",
            description="I am locked out after MFA setup and payroll closes today.",
        ).model_dump()
    )
    graph = SupportTriageGraph(SupportKnowledgeBase(), MockSupportChatModel())

    report = graph.run(ticket, trace_id="trace-test")

    assert report.category == TicketCategory.ACCOUNT
    assert report.priority == TicketPriority.HIGH
    assert report.confidence > 0.7
    assert report.escalate is True
    assert "risk_review" in report.workflow_path
    assert report.draft_response


def test_graph_keeps_general_question_low_priority() -> None:
    ticket = Ticket(
        **TicketCreate(
            customer_id="cust_456",
            subject="Question about changing notification settings",
            description="How do I update email notification preferences for weekly reports?",
        ).model_dump()
    )
    graph = SupportTriageGraph(SupportKnowledgeBase(), MockSupportChatModel())

    report = graph.run(ticket, trace_id="trace-test")

    assert report.category == TicketCategory.GENERAL
    assert report.priority == TicketPriority.LOW
    assert report.escalate is False
    assert "risk_review" not in report.workflow_path


def test_security_terms_take_precedence_over_account_terms() -> None:
    ticket = Ticket(
        **TicketCreate(
            customer_id="cust_789",
            subject="Suspicious account compromise",
            description="We suspect account compromise after a phishing email and unusual login.",
        ).model_dump()
    )
    graph = SupportTriageGraph(SupportKnowledgeBase(), MockSupportChatModel())

    report = graph.run(ticket, trace_id="trace-test")

    assert report.category == TicketCategory.SECURITY
    assert report.priority == TicketPriority.CRITICAL
    assert report.escalate is True
