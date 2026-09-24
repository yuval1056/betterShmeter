import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.services.git_service import mcp_client
from app.storage.db import create_connection
from app.storage.repository import MessageRepository

# Note: don't run this app with `uvicorn --reload` (or --workers > 1) on
# Windows. uvicorn forces the Selector event loop for those modes there
# (see uvicorn/loops/asyncio.py), and Selector doesn't support asyncio
# subprocesses on Windows -- which the GitHub MCP connection needs. This
# is set before the app is even imported, so it can't be worked around
# from here; run without --reload instead.

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Constructed once per process -- every request shares this one
    # repository instance, which is what makes its write lock effective.
    app.state.repository = MessageRepository(create_connection())

    # Logged via uvicorn's logger so it shows up in the server console.
    if settings.PROXY_API_KEY:
        logger.info(
            "LLM model: %s (endpoint: %s)",
            settings.PROXY_MODEL_NAME or "<not set>",
            settings.PROXY_BASE_URL or "<not set>",
        )
    else:
        logger.warning("No PROXY_API_KEY set -- replies will be simulated (model: %s)", settings.PROXY_MODEL_NAME or "<not set>")

    # GitHub MCP subprocesses are spawned lazily per user (each brings their
    # own token) and torn down on shutdown.
    try:
        yield
    finally:
        await mcp_client.disconnect_all()


app = FastAPI(title="Better Shmeter", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.API_PREFIX)
