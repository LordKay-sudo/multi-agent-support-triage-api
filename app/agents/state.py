import operator
from typing import Annotated, TypedDict

from app.models.tickets import AgentEvent, TicketCategory, TicketPriority


class TriageState(TypedDict, total=False):
    ticket_id: str
    customer_id: str
    subject: str
    description: str
    channel: str
    category: TicketCategory
    priority: TicketPriority
    confidence: float
    guidance: list[str]
    recommended_actions: list[str]
    draft_response: str
    escalate: bool
    rationale: str
    requires_risk_review: bool
    workflow_path: Annotated[list[str], operator.add]
    events: Annotated[list[AgentEvent], operator.add]
