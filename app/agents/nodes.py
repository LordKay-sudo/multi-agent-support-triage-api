from langchain_core.prompts import ChatPromptTemplate

from app.agents.state import TriageState
from app.models.tickets import AgentEvent, TicketCategory, TicketPriority
from app.services.knowledge_base import SupportKnowledgeBase
from app.services.llm import SupportChatModel


class SupportTriageAgents:
    def __init__(self, knowledge_base: SupportKnowledgeBase, chat_model: SupportChatModel) -> None:
        self._knowledge_base = knowledge_base
        self._chat_model = chat_model

    def classify(self, state: TriageState) -> TriageState:
        text = self._ticket_text(state)
        category = self._classify_category(text)
        priority = self._classify_priority(text, category)
        confidence = self._classification_confidence(text, category, priority)
        requires_risk_review = priority in {TicketPriority.HIGH, TicketPriority.CRITICAL}

        return {
            "category": category,
            "priority": priority,
            "confidence": confidence,
            "requires_risk_review": requires_risk_review,
            "workflow_path": ["classifier"],
            "events": [
                AgentEvent(
                    agent="classifier",
                    summary=(
                        f"Classified ticket as {category.value} "
                        f"with {priority.value} priority."
                    ),
                    metadata={"confidence": f"{confidence:.2f}"},
                )
            ],
        }

    def supervise(self, state: TriageState) -> TriageState:
        next_step = "risk_review" if state.get("requires_risk_review") else "retrieval"
        return {
            "workflow_path": ["supervisor"],
            "events": [
                AgentEvent(
                    agent="supervisor",
                    summary=f"Selected {next_step} as the next agent.",
                    metadata={"next": next_step},
                )
            ],
        }

    def risk_review(self, state: TriageState) -> TriageState:
        category = state["category"]
        actions = [
            "Route to a senior support owner for same-day review.",
            "Preserve audit context and customer communications.",
        ]
        if category == TicketCategory.SECURITY:
            actions.append("Open a security incident candidate and check account access logs.")

        return {
            "recommended_actions": actions,
            "workflow_path": ["risk_review"],
            "events": [
                AgentEvent(
                    agent="risk_review",
                    summary="Added risk controls for a high-impact ticket.",
                )
            ],
        }

    def retrieve_guidance(self, state: TriageState) -> TriageState:
        category = state.get("category", TicketCategory.GENERAL)
        guidance = self._knowledge_base.lookup(category)
        return {
            "guidance": guidance,
            "workflow_path": ["retrieval"],
            "events": [
                AgentEvent(
                    agent="retrieval",
                    summary=f"Retrieved {len(guidance)} support guidance snippets.",
                )
            ],
        }

    def plan_actions(self, state: TriageState) -> TriageState:
        base_actions = list(state.get("recommended_actions", []))
        category = state.get("category", TicketCategory.GENERAL)
        priority = state.get("priority", TicketPriority.MEDIUM)

        category_actions = {
            TicketCategory.BILLING: [
                "Check billing history and payment provider events.",
                "Confirm whether refund, credit, or invoice correction is appropriate.",
            ],
            TicketCategory.TECHNICAL: [
                "Collect reproduction steps, screenshots, and affected environment.",
                "Check known incidents and recent deployments.",
            ],
            TicketCategory.ACCOUNT: [
                "Verify identity before changing account access.",
                "Send secure account recovery instructions.",
            ],
            TicketCategory.SECURITY: [
                "Lock down suspicious sessions if compromise is plausible.",
                "Escalate confirmed compromise to the security queue.",
            ],
            TicketCategory.GENERAL: [
                "Ask for any missing context needed to resolve the request.",
                "Set a clear response window for the customer.",
            ],
        }
        priority_action = f"Respond using the {priority.value} priority support SLA."
        fallback_actions = category_actions[TicketCategory.GENERAL]
        actions = [*base_actions, *category_actions.get(category, fallback_actions)]
        actions.append(priority_action)

        return {
            "recommended_actions": actions,
            "workflow_path": ["planner"],
            "events": [
                AgentEvent(
                    agent="planner",
                    summary=f"Created {len(actions)} recommended actions.",
                )
            ],
        }

    def draft_response(self, state: TriageState) -> TriageState:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a careful support agent. Draft concise, accurate customer updates.",
                ),
                (
                    "human",
                    "Subject: {subject}\n"
                    "Description: {description}\n"
                    "Category: {category}\n"
                    "Priority: {priority}\n"
                    "Actions: {actions}\n"
                    "Guidance: {guidance}\n\n"
                    "Draft a response that acknowledges the issue and explains the next step.",
                ),
            ]
        )
        messages = prompt.format_messages(
            subject=state["subject"],
            description=state["description"],
            category=state.get("category", TicketCategory.GENERAL).value,
            priority=state.get("priority", TicketPriority.MEDIUM).value,
            actions="; ".join(state.get("recommended_actions", [])),
            guidance="; ".join(state.get("guidance", [])),
        )

        return {
            "draft_response": self._chat_model.invoke(messages),
            "workflow_path": ["drafting"],
            "events": [
                AgentEvent(
                    agent="drafting",
                    summary=(
                        "Drafted the customer-facing response "
                        "with LangChain prompt formatting."
                    ),
                )
            ],
        }

    def decide_escalation(self, state: TriageState) -> TriageState:
        priority = state.get("priority", TicketPriority.MEDIUM)
        category = state.get("category", TicketCategory.GENERAL)
        escalate = priority in {TicketPriority.HIGH, TicketPriority.CRITICAL}
        rationale = (
            f"Escalation is {'required' if escalate else 'not required'} because the ticket is "
            f"{priority.value} priority in the {category.value} queue."
        )

        return {
            "escalate": escalate,
            "rationale": rationale,
            "workflow_path": ["escalation"],
            "events": [
                AgentEvent(
                    agent="escalation",
                    summary=rationale,
                )
            ],
        }

    @staticmethod
    def _ticket_text(state: TriageState) -> str:
        return f"{state['subject']} {state['description']}".lower()

    @staticmethod
    def _classify_category(text: str) -> TicketCategory:
        if any(term in text for term in ["breach", "compromise", "phishing", "suspicious"]):
            return TicketCategory.SECURITY
        if any(term in text for term in ["error", "bug", "down", "latency", "api", "crash"]):
            return TicketCategory.TECHNICAL
        if any(term in text for term in ["invoice", "payment", "refund", "charge", "billing"]):
            return TicketCategory.BILLING
        if any(term in text for term in ["mfa", "password", "login", "locked", "account"]):
            return TicketCategory.ACCOUNT
        return TicketCategory.GENERAL

    @staticmethod
    def _classify_priority(text: str, category: TicketCategory) -> TicketPriority:
        if any(term in text for term in ["breach", "compromise", "data leak", "production down"]):
            return TicketPriority.CRITICAL
        if category == TicketCategory.SECURITY:
            return TicketPriority.HIGH
        if any(term in text for term in ["urgent", "blocked", "payroll", "angry", "cannot access"]):
            return TicketPriority.HIGH
        if any(term in text for term in ["question", "how do i", "request"]):
            return TicketPriority.LOW
        return TicketPriority.MEDIUM

    @staticmethod
    def _classification_confidence(
        text: str,
        category: TicketCategory,
        priority: TicketPriority,
    ) -> float:
        category_terms = {
            TicketCategory.BILLING: ["invoice", "payment", "refund", "charge", "billing"],
            TicketCategory.TECHNICAL: ["error", "bug", "down", "latency", "api", "crash"],
            TicketCategory.ACCOUNT: ["mfa", "password", "login", "locked", "account"],
            TicketCategory.SECURITY: ["breach", "compromise", "phishing", "suspicious"],
            TicketCategory.GENERAL: [],
        }
        category_hits = sum(term in text for term in category_terms[category])
        priority_bonus = 0.08 if priority in {TicketPriority.HIGH, TicketPriority.CRITICAL} else 0
        confidence = 0.62 + min(category_hits * 0.08, 0.24) + priority_bonus
        return round(min(confidence, 0.94), 2)
