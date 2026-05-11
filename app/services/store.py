from datetime import UTC, datetime
from threading import RLock
from uuid import UUID

from app.models.tickets import Ticket, TicketCreate, TicketStatus, TriageReport


class TicketNotFoundError(KeyError):
    pass


class TicketStore:
    """In-memory store keeps the demo runnable without external infrastructure."""

    def __init__(self) -> None:
        self._tickets: dict[UUID, Ticket] = {}
        self._lock = RLock()

    def create(self, payload: TicketCreate) -> Ticket:
        ticket = Ticket(**payload.model_dump())
        with self._lock:
            self._tickets[ticket.id] = ticket
        return ticket

    def get(self, ticket_id: UUID) -> Ticket:
        with self._lock:
            try:
                return self._tickets[ticket_id]
            except KeyError as exc:
                raise TicketNotFoundError(str(ticket_id)) from exc

    def save_report(self, ticket_id: UUID, report: TriageReport) -> Ticket:
        with self._lock:
            try:
                ticket = self._tickets[ticket_id]
            except KeyError as exc:
                raise TicketNotFoundError(str(ticket_id)) from exc

            updated = ticket.model_copy(
                update={
                    "status": TicketStatus.TRIAGED,
                    "report": report,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._tickets[ticket_id] = updated
        return updated
