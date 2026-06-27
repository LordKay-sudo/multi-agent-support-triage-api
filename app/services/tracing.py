import logging
import os
from typing import Any
from uuid import uuid4

from app.core.config import Settings
from app.models.tickets import Ticket, TriageReport

logger = logging.getLogger(__name__)


class TriageTracer:
    """Records per-agent Langfuse spans during graph execution."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._request_id: str | None = None
        self._root_cm: Any = None
        self._root_span: Any = None

    def new_trace_id(self, request_id: str | None = None) -> str:
        if request_id:
            return request_id
        return f"triage-{uuid4()}"

    def begin_run(self, trace_id: str, ticket: Ticket, request_id: str | None = None) -> None:
        self._request_id = request_id
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
            self._root_cm = langfuse.start_as_current_span(name="support-triage-run")
            self._root_span = self._root_cm.__enter__()
            self._root_span.update(
                input={
                    "ticket_id": str(ticket.id),
                    "customer_id": ticket.customer_id,
                    "subject": ticket.subject,
                    "description": ticket.description,
                },
                metadata={
                    "trace_id": trace_id,
                    "request_id": request_id,
                },
            )
            self._root_span.update_trace(
                session_id=str(ticket.id),
                user_id=ticket.customer_id,
                tags=["support-triage"],
            )
        except Exception:
            logger.exception("Failed to start Langfuse trace")
            self._close_root_span()

    def record_node(
        self,
        node_name: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
    ) -> None:
        if not self._is_configured() or self._root_span is None:
            return

        try:
            from langfuse import get_client

            langfuse = get_client()
            with langfuse.start_as_current_span(name=f"agent:{node_name}") as span:
                span.update(input=input_data, output=output_data)
        except Exception:
            logger.exception("Failed to record Langfuse span for node %s", node_name)

    def end_run(self, ticket: Ticket, report: TriageReport) -> None:
        if self._is_configured() and self._root_span is not None:
            try:
                self._root_span.update(
                    output=report.model_dump(mode="json"),
                    metadata={
                        "category": report.category.value,
                        "priority": report.priority.value,
                        "trace_id": report.trace_id,
                        "request_id": self._request_id,
                    },
                )
                self._root_span.update_trace(
                    session_id=str(ticket.id),
                    user_id=ticket.customer_id,
                    tags=["support-triage", report.category.value, report.priority.value],
                )
            except Exception:
                logger.exception("Failed to finalize Langfuse trace")
            finally:
                self._close_root_span()
                self._flush_langfuse()

        self._request_id = None

    def record_failure(self, ticket: Ticket, trace_id: str, error: str) -> None:
        if not self._is_configured():
            return

        try:
            if self._root_span is not None:
                self._root_span.update(
                    output={"error": error, "trace_id": trace_id},
                    metadata={"status": "failed", "request_id": self._request_id},
                )
                self._root_span.update_trace(
                    session_id=str(ticket.id),
                    user_id=ticket.customer_id,
                    tags=["support-triage", "failed"],
                )
            else:
                from langfuse import get_client

                self._export_langfuse_env()
                langfuse = get_client()
                with langfuse.start_as_current_span(name="support-triage-failed") as span:
                    span.update(
                        input={"ticket_id": str(ticket.id), "trace_id": trace_id},
                        output={"error": error},
                        metadata={"status": "failed", "request_id": self._request_id},
                    )
                    span.update_trace(
                        session_id=str(ticket.id),
                        user_id=ticket.customer_id,
                        tags=["support-triage", "failed"],
                    )
        except Exception:
            logger.exception("Failed to export triage failure to Langfuse")
        finally:
            self._close_root_span()
            self._flush_langfuse()
            self._request_id = None

    def _close_root_span(self) -> None:
        if self._root_cm is None:
            return
        try:
            self._root_cm.__exit__(None, None, None)
        except Exception:
            logger.exception("Failed to close Langfuse root span")
        finally:
            self._root_cm = None
            self._root_span = None

    def _flush_langfuse(self) -> None:
        try:
            from langfuse import get_client

            get_client().flush()
        except Exception:
            logger.exception("Failed to flush Langfuse client")

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
