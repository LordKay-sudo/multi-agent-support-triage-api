from functools import lru_cache

from app.agents.graph import SupportTriageGraph
from app.core.config import get_settings
from app.services.knowledge_base import SupportKnowledgeBase
from app.services.llm import build_chat_model
from app.services.store import TicketStore
from app.services.tracing import TriageTracer


@lru_cache
def get_store() -> TicketStore:
    return TicketStore()


@lru_cache
def get_triage_graph() -> SupportTriageGraph:
    settings = get_settings()
    return SupportTriageGraph(
        knowledge_base=SupportKnowledgeBase(),
        triage_model=build_chat_model(settings),
        tracer=get_tracer(),
    )


@lru_cache
def get_tracer() -> TriageTracer:
    return TriageTracer(get_settings())
