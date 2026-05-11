from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.agents.graph import SupportTriageGraph
from app.core.config import Settings, get_settings
from app.dependencies import get_store, get_tracer, get_triage_graph
from app.models.tickets import HealthResponse, TicketCreate, TicketResponse, TicketStatus
from app.services.store import TicketNotFoundError, TicketStore
from app.services.tracing import TriageTracer

health_router = APIRouter(tags=["health"])
tickets_router = APIRouter(prefix="/tickets", tags=["tickets"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
StoreDep = Annotated[TicketStore, Depends(get_store)]
GraphDep = Annotated[SupportTriageGraph, Depends(get_triage_graph)]
TracerDep = Annotated[TriageTracer, Depends(get_tracer)]
ForceQuery = Annotated[
    bool,
    Query(description="Re-run triage even if a report already exists."),
]


@health_router.get("/health", response_model=HealthResponse)
def health(settings: SettingsDep) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        llm_provider=settings.llm_provider,
        langfuse_enabled=settings.langfuse_enabled,
    )


@tickets_router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate,
    store: StoreDep,
) -> TicketResponse:
    return TicketResponse.model_validate(store.create(payload))


@tickets_router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: UUID,
    store: StoreDep,
) -> TicketResponse:
    try:
        return TicketResponse.model_validate(store.get(ticket_id))
    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        ) from exc


@tickets_router.post("/{ticket_id}/triage", response_model=TicketResponse)
def run_triage(
    ticket_id: UUID,
    store: StoreDep,
    graph: GraphDep,
    tracer: TracerDep,
    force: ForceQuery = False,
) -> TicketResponse:
    try:
        ticket = store.get(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        ) from exc

    if ticket.status == TicketStatus.TRIAGED and ticket.report is not None and not force:
        return TicketResponse.model_validate(ticket)

    report = graph.run(ticket, trace_id=tracer.new_trace_id())
    updated_ticket = store.save_report(ticket.id, report)
    tracer.record(updated_ticket, report)
    return TicketResponse.model_validate(updated_ticket)
