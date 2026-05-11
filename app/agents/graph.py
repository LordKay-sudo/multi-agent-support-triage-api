from langgraph.graph import END, START, StateGraph

from app.agents.nodes import SupportTriageAgents
from app.agents.state import TriageState
from app.models.tickets import Ticket, TicketCategory, TicketPriority, TriageReport
from app.services.knowledge_base import SupportKnowledgeBase
from app.services.llm import SupportChatModel


class SupportTriageGraph:
    def __init__(self, knowledge_base: SupportKnowledgeBase, chat_model: SupportChatModel) -> None:
        self._agents = SupportTriageAgents(knowledge_base, chat_model)
        self._graph = self._build_graph()

    def run(self, ticket: Ticket, trace_id: str) -> TriageReport:
        initial_state: TriageState = {
            "ticket_id": str(ticket.id),
            "customer_id": ticket.customer_id,
            "subject": ticket.subject,
            "description": ticket.description,
            "channel": ticket.channel,
            "workflow_path": [],
            "events": [],
        }
        result = self._graph.invoke(initial_state)

        return TriageReport(
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

    def _build_graph(self):
        workflow = StateGraph(TriageState)
        workflow.add_node("classify", self._agents.classify)
        workflow.add_node("supervise", self._agents.supervise)
        workflow.add_node("risk_review", self._agents.risk_review)
        workflow.add_node("retrieve_guidance", self._agents.retrieve_guidance)
        workflow.add_node("plan_actions", self._agents.plan_actions)
        workflow.add_node("draft_response", self._agents.draft_response)
        workflow.add_node("decide_escalation", self._agents.decide_escalation)

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

    @staticmethod
    def _route_after_supervisor(state: TriageState) -> str:
        return "risk_review" if state.get("requires_risk_review") else "retrieval"
