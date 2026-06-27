from langgraph.graph import END, START, StateGraph

from app.agents.nodes import SupportTriageAgents
from app.agents.state import TriageState
from app.models.tickets import Ticket, TicketCategory, TicketPriority, TriageReport
from app.services.knowledge_base import SupportKnowledgeBase
from app.services.llm import SupportTriageModel
from app.services.tracing import TriageTracer
from app.services.triage_errors import TriageError


class SupportTriageGraph:
    def __init__(
        self,
        knowledge_base: SupportKnowledgeBase,
        triage_model: SupportTriageModel,
        tracer: TriageTracer | None = None,
    ) -> None:
        self._tracer = tracer
        self._agents = SupportTriageAgents(knowledge_base, triage_model)
        self._graph = self._build_graph()

    def run(self, ticket: Ticket, trace_id: str, request_id: str | None = None) -> TriageReport:
        if self._tracer is not None:
            self._tracer.begin_run(trace_id, ticket, request_id=request_id)

        initial_state: TriageState = {
            "ticket_id": str(ticket.id),
            "customer_id": ticket.customer_id,
            "subject": ticket.subject,
            "description": ticket.description,
            "channel": ticket.channel,
            "workflow_path": [],
            "events": [],
        }

        try:
            result = self._graph.invoke(initial_state)
        except Exception as exc:
            if self._tracer is not None:
                self._tracer.record_failure(ticket, trace_id, str(exc))
            raise TriageError(str(exc)) from exc

        report = TriageReport(
            category=result.get("category", TicketCategory.GENERAL),
            priority=result.get("priority", TicketPriority.MEDIUM),
            confidence=result.get("confidence", 0.0),
            guidance=result.get("guidance", []),
            recommended_actions=result.get("recommended_actions", []),
            draft_response=result.get("draft_response", ""),
            escalate=result.get("escalate", False),
            rationale=result.get("rationale", ""),
            workflow_path=result.get("workflow_path", []),
            trace_id=trace_id,
            events=result.get("events", []),
        )

        if self._tracer is not None:
            self._tracer.end_run(ticket, report)

        return report

    def _build_graph(self):
        workflow = StateGraph(TriageState)
        workflow.add_node("classify", self._instrument_node("classify", self._agents.classify))
        workflow.add_node("supervise", self._instrument_node("supervise", self._agents.supervise))
        workflow.add_node(
            "risk_review",
            self._instrument_node("risk_review", self._agents.risk_review),
        )
        workflow.add_node(
            "retrieve_guidance",
            self._instrument_node("retrieve_guidance", self._agents.retrieve_guidance),
        )
        workflow.add_node(
            "plan_actions",
            self._instrument_node("plan_actions", self._agents.plan_actions),
        )
        workflow.add_node(
            "draft_response",
            self._instrument_node("draft_response", self._agents.draft_response),
        )
        workflow.add_node(
            "decide_escalation",
            self._instrument_node("decide_escalation", self._agents.decide_escalation),
        )

        workflow.add_edge(START, "classify")
        workflow.add_edge("classify", "supervise")
        workflow.add_conditional_edges(
            "supervise",
            self._route_after_supervisor,
            {
                "risk_review": "risk_review",
                "retrieval": "retrieve_guidance",
            },
        )
        workflow.add_edge("risk_review", "retrieve_guidance")
        workflow.add_edge("retrieve_guidance", "plan_actions")
        workflow.add_edge("plan_actions", "draft_response")
        workflow.add_edge("draft_response", "decide_escalation")
        workflow.add_edge("decide_escalation", END)
        return workflow.compile()

    def _instrument_node(self, node_name: str, handler):
        def node(state: TriageState) -> TriageState:
            result = handler(state)
            if self._tracer is not None:
                self._tracer.record_node(
                    node_name,
                    input_data=_node_input(state),
                    output_data=_node_output(result),
                )
            return result

        return node

    @staticmethod
    def _route_after_supervisor(state: TriageState) -> str:
        return "risk_review" if state.get("requires_risk_review") else "retrieval"


def _node_input(state: TriageState) -> dict[str, object]:
    return {
        "ticket_id": state.get("ticket_id"),
        "subject": state.get("subject"),
        "description": state.get("description"),
        "category": getattr(state.get("category"), "value", state.get("category")),
        "priority": getattr(state.get("priority"), "value", state.get("priority")),
        "requires_risk_review": state.get("requires_risk_review"),
        "recommended_actions": state.get("recommended_actions", []),
        "guidance": state.get("guidance", []),
    }


def _node_output(result: TriageState) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key in (
        "category",
        "priority",
        "confidence",
        "requires_risk_review",
        "guidance",
        "recommended_actions",
        "draft_response",
        "escalate",
        "rationale",
        "workflow_path",
    ):
        if key in result:
            value = result[key]
            if hasattr(value, "value"):
                payload[key] = value.value
            else:
                payload[key] = value
    if "events" in result:
        payload["events"] = [event.model_dump(mode="json") for event in result["events"]]
    return payload
