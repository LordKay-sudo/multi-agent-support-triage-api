import logging
import os
from uuid import uuid4

from app.core.config import Settings
from app.models.tickets import Ticket, TriageReport

logger = logging.getLogger(__name__)


class TriageTracer:
    """Records a Langfuse trace when configured, otherwise returns local trace ids."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def new_trace_id(self) -> str:
        return f"triage-{uuid4()}"

    def record(self, ticket: Ticket, report: TriageReport) -> None:
        if not self._is_configured():
            return

        try:
            from langfuse import get_client
        except ImportError:
            logger.warning("Langfuse is enabled but the SDK is not installed")
            return

        try:
            self._export_langfuse_env()
            langfuse = get_client()
            with langfuse.start_as_current_span(name="support-triage-run") as span:
                span.update(
                    input={
                        "ticket_id": str(ticket.id),
                        "customer_id": ticket.customer_id,
                        "subject": ticket.subject,
                        "description": ticket.description,
                    },
                    output=report.model_dump(mode="json"),
                    metadata={
                        "category": report.category.value,
                        "priority": report.priority.value,
                        "trace_id": report.trace_id,
                    },
                )
                span.update_trace(
                    session_id=str(ticket.id),
                    user_id=ticket.customer_id,
                    tags=["support-triage", report.category.value, report.priority.value],
                )
                for event in report.events:
                    with langfuse.start_as_current_span(name=f"agent:{event.agent}") as child:
                        child.update(output=event.model_dump(mode="json"))
            langfuse.flush()
        except Exception:
            logger.exception("Failed to export triage trace to Langfuse")

    def _is_configured(self) -> bool:
        if not self._settings.langfuse_enabled:
            return False
        if not self._settings.langfuse_public_key or not self._settings.langfuse_secret_key:
            logger.warning("Langfuse is enabled but public/secret keys are missing")
            return False
        return True

    def _export_langfuse_env(self) -> None:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", self._settings.langfuse_public_key or "")
        os.environ.setdefault("LANGFUSE_SECRET_KEY", self._settings.langfuse_secret_key or "")
        os.environ.setdefault("LANGFUSE_HOST", self._settings.langfuse_host)
