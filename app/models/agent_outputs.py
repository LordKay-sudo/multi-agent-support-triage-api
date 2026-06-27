from pydantic import Field

from app.models.tickets import StrictBaseModel, TicketCategory, TicketPriority


class ClassificationResult(StrictBaseModel):
    category: TicketCategory
    priority: TicketPriority
    confidence: float = Field(..., ge=0, le=1)


class EscalationDecision(StrictBaseModel):
    escalate: bool
    rationale: str = Field(..., min_length=10, max_length=500)
