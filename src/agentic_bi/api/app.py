"""FastAPI application for the Agentic Business Intelligence system."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agentic_bi.api.schemas import AskRequest, AskResponse
from agentic_bi.config import (
    FRONTEND_DIR,
    OPTIONAL_SETTINGS,
    missing_settings,
    validate_settings,
)
from agentic_bi.core.agent import run_agent

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Refuse to start without the required settings."""

    validate_settings()

    for name in missing_settings(OPTIONAL_SETTINGS):
        logger.warning("%s is not set; official-web answers will fail.", name)

    yield


app = FastAPI(
    lifespan=lifespan,
    title="Agentic Business Intelligence",
    description=(
        "Agentic BI API for structured flight-data analysis, "
        "private-document knowledge retrieval, and trusted "
        "current airline information."
    ),
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------


@app.middleware("http")
async def revalidate_frontend(request, call_next):
    """
    Make browsers revalidate the frontend on every load.

    Without Cache-Control, browsers may heuristically reuse an old
    index.html alongside a newer stylesheet. ETags keep revalidation
    cheap (304 Not Modified when nothing changed).
    """

    response = await call_next(request)

    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"

    return response


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    """Serve the Agentic BI web interface."""

    return FileResponse(FRONTEND_DIR / "index.html")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    """Return the API health status."""

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


@app.post("/ask", response_model=AskResponse)
def ask_agent(request: AskRequest) -> AskResponse:
    """Run the BI agent for a user question."""

    result = run_agent(question=request.question, verbose=False)

    if result.trace is None:
        raise RuntimeError("Agent execution completed without a trace.")

    return AskResponse(
        answer=result.final_answer,
        selected_skill=result.selected_skill,
        stop_reason=result.stop_reason,
        run_id=result.trace.run_id,
        step_count=result.step_count,
        tool_call_count=result.tool_call_count,
        knowledge_search_count=result.knowledge_search_count,
        data_analysis_count=result.data_analysis_count,
        web_search_count=result.web_search_count,
        error_count=len(result.errors),
        sources=result.sources,
    )
