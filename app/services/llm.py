from collections.abc import Sequence
from typing import Any, Protocol

from langchain_core.messages import AIMessage, BaseMessage

from app.core.config import Settings


class SupportChatModel(Protocol):
    def invoke(self, messages: Sequence[BaseMessage]) -> str:
        """Return assistant text for a formatted LangChain chat prompt."""


class MockSupportChatModel:
    """Deterministic model for local demos, CI, and portfolio screenshots."""

    def invoke(self, messages: Sequence[BaseMessage]) -> str:
        return (
            "Thanks for contacting support. We have reviewed the details and prioritised this "
            "case based on impact and risk. Our next step is to validate the account context, "
            "check the relevant support guidance, and keep you updated until the issue is resolved."
        )


class BedrockSupportChatModel:
    """LangChain adapter for AWS Bedrock chat models."""

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


def build_chat_model(settings: Settings) -> SupportChatModel:
    if settings.llm_provider == "bedrock":
        return BedrockSupportChatModel(settings)
    return MockSupportChatModel()


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
