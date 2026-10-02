"""FastAPI application for the Agentic Business Intelligence system."""

import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from agentic_bi.api.charts import build_charts
from agentic_bi.api.schemas import AskRequest, AskResponse
from agentic_bi.config import (
    FRONTEND_DIR,
    OPTIONAL_SETTINGS,
    ConfigError,
    missing_settings,
    validate_settings,
    warm_up_on_startup,
)
from agentic_bi.core.agent import run_agent
from agentic_bi.tools.warmup import warm_up_tools

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Check settings, then load models so the first question is fast."""

    validate_settings()

    for name in missing_settings(OPTIONAL_SETTINGS):
        logger.warning("%s is not set; official-web answers will fail.", name)

    if warm_up_on_startup():
        for name, seconds in warm_up_tools().items():
            logger.info("Loaded %s in %.1fs", name, seconds)

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


def _error_response(status_code: int, message: str, error_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": f"{message} (reference {error_id})", "error_id": error_id},
    )


@app.post(
    "/ask",
    response_model=AskResponse,
    responses={500: {"description": "The agent failed; see error_id in the logs."}},
)
def ask_agent(request: AskRequest) -> AskResponse | JSONResponse:
    """Run the BI agent for a user question."""

    error_id = uuid4().hex[:12]

    try:
        result = run_agent(question=request.question, verbose=False)

    except ConfigError as exc:
        logger.error("Configuration error [%s]: %s", error_id, exc)
        return _error_response(503, "The service is not configured.", error_id)

    except Exception:
        # Full details go to the server log, never to the client.
        logger.exception("Agent run failed [%s]", error_id)
        return _error_response(
            500, "Something went wrong while answering. Please try again.", error_id
        )

    if result.trace is None:
        logger.error("Agent run finished without a trace [%s]", error_id)
        return _error_response(500, "The answer could not be recorded.", error_id)

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
        charts=build_charts(result.observations),
    )
