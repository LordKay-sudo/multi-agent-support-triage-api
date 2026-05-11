from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class TicketCategory(StrEnum):
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    SECURITY = "security"
    GENERAL = "general"


class TicketPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketStatus(StrEnum):
    OPEN = "open"
    TRIAGED = "triaged"
    FAILED = "failed"


class SupportChannel(StrEnum):
    EMAIL = "email"
    CHAT = "chat"
    PHONE = "phone"
    WEB = "web"


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TicketCreate(StrictBaseModel):
    customer_id: str = Field(..., min_length=3, max_length=80, examples=["cust_123"])
    subject: str = Field(..., min_length=3, max_length=160, examples=["Cannot access my account"])
    description: str = Field(
        ...,
        min_length=10,
        max_length=4000,
        examples=[
            "I am locked out after enabling MFA and need urgent access before payroll closes."
        ],
    )
    channel: SupportChannel = Field(
        default=SupportChannel.EMAIL,
        examples=["email", "chat", "phone"],
    )


class Ticket(StrictBaseModel):
    id: UUID = Field(default_factory=uuid4)
    customer_id: str
    subject: str
    description: str
    channel: SupportChannel = SupportChannel.EMAIL
    status: TicketStatus = TicketStatus.OPEN
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    report: "TriageReport | None" = None


class AgentEvent(StrictBaseModel):
    agent: str
    summary: str
    metadata: dict[str, str] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TriageReport(StrictBaseModel):
    category: TicketCategory
    priority: TicketPriority
    confidence: float = Field(..., ge=0, le=1)
    guidance: list[str]
    recommended_actions: list[str]
    draft_response: str
    escalate: bool
    rationale: str
    workflow_path: list[str]
    trace_id: str
    events: list[AgentEvent]


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: str
    subject: str
    description: str
    channel: SupportChannel
    status: TicketStatus
    created_at: datetime
    updated_at: datetime
    report: TriageReport | None


class HealthResponse(StrictBaseModel):
    status: str
    service: str
    version: str
    environment: str
    llm_provider: str
    langfuse_enabled: bool
