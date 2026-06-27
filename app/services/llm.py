from collections.abc import Sequence
from typing import Any, Protocol

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate

from app.agents.classification_rules import classify_ticket, decide_escalation
from app.core.config import Settings
from app.models.agent_outputs import ClassificationResult, EscalationDecision
from app.models.tickets import TicketCategory, TicketPriority


class SupportTriageModel(Protocol):
    def invoke(self, messages: Sequence[BaseMessage]) -> str:
        """Return assistant text for a formatted LangChain chat prompt."""

    def classify_ticket(self, subject: str, description: str) -> ClassificationResult:
        """Return structured classification for a support ticket."""

    def decide_escalation(
        self,
        subject: str,
        description: str,
        category: TicketCategory,
        priority: TicketPriority,
        recommended_actions: list[str],
        guidance: list[str],
    ) -> EscalationDecision:
        """Return a structured escalation decision for a support ticket."""


class MockSupportTriageModel:
    """Deterministic model for local demos, CI, evals, and portfolio screenshots."""

    def invoke(self, messages: Sequence[BaseMessage]) -> str:
        return (
            "Thanks for contacting support. We have reviewed the details and prioritised this "
            "case based on impact and risk. Our next step is to validate the account context, "
            "check the relevant support guidance, and keep you updated until the issue is resolved."
        )

    def classify_ticket(self, subject: str, description: str) -> ClassificationResult:
        return classify_ticket(subject, description)

    def decide_escalation(
        self,
        subject: str,
        description: str,
        category: TicketCategory,
        priority: TicketPriority,
        recommended_actions: list[str],
        guidance: list[str],
    ) -> EscalationDecision:
        _ = (subject, description, recommended_actions, guidance)
        return decide_escalation(category, priority)


class BedrockSupportTriageModel:
    """LangChain adapter for AWS Bedrock chat models with structured agent outputs."""

    def __init__(self, settings: Settings) -> None:
        try:
            from langchain_aws import ChatBedrockConverse
        except ImportError as exc:
            raise RuntimeError(
                "Install the Bedrock extra with `pip install -e '.[bedrock]'` to use AWS Bedrock."
            ) from exc

        self._model = ChatBedrockConverse(
            model=settings.bedrock_model_id,
            region_name=settings.aws_region,
            temperature=0,
        )

    def invoke(self, messages: Sequence[BaseMessage]) -> str:
        response = self._model.invoke(list(messages))
        if isinstance(response, AIMessage):
            return _stringify_content(response.content)
        return str(response)

    def classify_ticket(self, subject: str, description: str) -> ClassificationResult:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You classify support tickets by category, priority, and confidence. "
                    "Categories: billing, technical, account, security, general. "
                    "Priorities: low, medium, high, critical.",
                ),
                (
                    "human",
                    "Subject: {subject}\nDescription: {description}\n\n"
                    "Return the best category, priority, and confidence between 0 and 1.",
                ),
            ]
        )
        try:
            chain = prompt | self._model.with_structured_output(ClassificationResult)
            return chain.invoke({"subject": subject, "description": description})
        except Exception:
            return classify_ticket(subject, description)

    def decide_escalation(
        self,
        subject: str,
        description: str,
        category: TicketCategory,
        priority: TicketPriority,
        recommended_actions: list[str],
        guidance: list[str],
    ) -> EscalationDecision:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You decide whether a support ticket should be escalated to a senior team. "
                    "Return escalate=true for high-impact, security-sensitive, "
                    "or blocked customers.",
                ),
                (
                    "human",
                    "Subject: {subject}\n"
                    "Description: {description}\n"
                    "Category: {category}\n"
                    "Priority: {priority}\n"
                    "Recommended actions: {actions}\n"
                    "Guidance: {guidance}\n\n"
                    "Should this ticket be escalated? Provide a concise rationale.",
                ),
            ]
        )
        try:
            chain = prompt | self._model.with_structured_output(EscalationDecision)
            return chain.invoke(
                {
                    "subject": subject,
                    "description": description,
                    "category": category.value,
                    "priority": priority.value,
                    "actions": "; ".join(recommended_actions),
                    "guidance": "; ".join(guidance),
                }
            )
        except Exception:
            return decide_escalation(category, priority)


# Backwards-compatible aliases used by existing tests and imports.
SupportChatModel = SupportTriageModel
MockSupportChatModel = MockSupportTriageModel
BedrockSupportChatModel = BedrockSupportTriageModel


def build_chat_model(settings: Settings) -> SupportTriageModel:
    if settings.llm_provider == "bedrock":
        return BedrockSupportTriageModel(settings)
    return MockSupportTriageModel()


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)
