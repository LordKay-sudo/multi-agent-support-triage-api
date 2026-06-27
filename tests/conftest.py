from collections.abc import Generator

import pytest

from app.dependencies import get_store, get_triage_graph


@pytest.fixture(autouse=True)
def reset_in_memory_store() -> Generator[None]:
    get_store.cache_clear()
    get_triage_graph.cache_clear()
    yield
    get_store.cache_clear()
    get_triage_graph.cache_clear()
