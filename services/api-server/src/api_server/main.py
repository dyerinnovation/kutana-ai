"""FastAPI application entry point for the Convene AI API server."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from api_server.middleware import setup_cors
from api_server.routes.agent_keys import router as agent_keys_router
from api_server.routes.agents import router as agents_router
from api_server.routes.auth import router as auth_router
from api_server.routes.health import router as health_router
from api_server.routes.meetings import router as meetings_router
from api_server.routes.tasks import router as tasks_router
from api_server.routes.token import router as token_router

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle.

    Logs startup/shutdown events and can be extended to initialise
    database connection pools, Redis clients, or background tasks.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control back to the ASGI server while the app is running.
    """
    logger.info("api-server starting up")
    yield
    logger.info("api-server shutting down")


app = FastAPI(
    title="Convene AI API",
    description=("REST and WebSocket API for the Convene AI meeting assistant"),
    version="0.1.0",
    lifespan=lifespan,
)

setup_cors(app)

app.include_router(health_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(meetings_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(agent_keys_router, prefix="/api/v1")
app.include_router(token_router, prefix="/api/v1")
