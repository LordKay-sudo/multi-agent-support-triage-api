from uuid import uuid4

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response

from app.api import health_router, tickets_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    api = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Multi-agent support ticket triage with FastAPI, Pydantic, "
            "LangGraph, LangChain, and Langfuse."
        ),
    )

    @api.middleware("http")
    async def add_request_id(request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid4()))
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    api.include_router(health_router)
    api.include_router(tickets_router, prefix=settings.api_prefix)
    return api


app = create_app()
