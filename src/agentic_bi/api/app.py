"""FastAPI application for the Agentic Business Intelligence system."""

import json
import logging
import queue
import threading
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agentic_bi.api.charts import build_charts
from agentic_bi.api.progress import progress_message
from agentic_bi.api.schemas import AskRequest, AskResponse, FeedbackRequest
from agentic_bi.config import (
    FEEDBACK_PATH,
    FRONTEND_DIR,
    OPTIONAL_SETTINGS,
    ConfigError,
    missing_settings,
    validate_settings,
    warm_up_on_startup,
)
from agentic_bi.core.agent import run_agent
from agentic_bi.core.persistence import utc_now_iso
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


class AgentFailure(Exception):
    """An agent run failed; carries the HTTP status and a safe message."""

    def __init__(self, status_code: int, message: str, error_id: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = f"{message} (reference {error_id})"
        self.error_id = error_id

    def payload(self) -> dict[str, str]:
        return {"detail": self.message, "error_id": self.error_id}


def _answer(request: AskRequest, on_event=None) -> AskResponse:
    """Run the agent and build the response; raises AgentFailure."""

    error_id = uuid4().hex[:12]

    try:
        result = run_agent(
            question=request.question,
            verbose=False,
            history=[message.model_dump() for message in request.history] or None,
            on_event=on_event,
        )

    except ConfigError as exc:
        logger.error("Configuration error [%s]: %s", error_id, exc)
        raise AgentFailure(503, "The service is not configured.", error_id) from exc

    except Exception as exc:
        # Full details go to the server log, never to the client.
        logger.exception("Agent run failed [%s]", error_id)
        raise AgentFailure(
            500, "Something went wrong while answering. Please try again.", error_id
        ) from exc

    if result.trace is None:
        logger.error("Agent run finished without a trace [%s]", error_id)
        raise AgentFailure(500, "The answer could not be recorded.", error_id)

    return AskResponse(
        answer=result.final_answer,
        question=result.goal,
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


@app.post(
    "/ask",
    response_model=AskResponse,
    responses={500: {"description": "The agent failed; see error_id in the logs."}},
)
def ask_agent(request: AskRequest) -> AskResponse | JSONResponse:
    """Run the BI agent for a user question."""

    try:
        return _answer(request)
    except AgentFailure as failure:
        return JSONResponse(status_code=failure.status_code, content=failure.payload())


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/ask/stream")
def ask_agent_stream(request: AskRequest) -> StreamingResponse:
    """
    Run the agent and stream Server-Sent Events while it works.

    Events: `progress` ({step, message}) as the agent moves through its
    stages, then exactly one `result` (the /ask response body) or `error`
    ({detail, error_id, status}).
    """

    events: queue.Queue[tuple[str, dict] | None] = queue.Queue()

    def on_event(event_type: str, data: dict) -> None:
        message = progress_message(event_type, data)

        if message:
            events.put(("progress", {"step": event_type, "message": message}))

    def work() -> None:
        try:
            response = _answer(request, on_event=on_event)
            events.put(("result", response.model_dump(mode="json")))
        except AgentFailure as failure:
            events.put(("error", {**failure.payload(), "status": failure.status_code}))
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while (item := events.get()) is not None:
            yield _sse(*item)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


@app.post("/feedback", status_code=204)
def record_feedback(feedback: FeedbackRequest) -> None:
    """Append a reader's rating of one answer to data/feedback.jsonl."""

    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)

    with FEEDBACK_PATH.open("a", encoding="utf-8") as file:
        file.write(
            json.dumps({"recorded_at": utc_now_iso(), **feedback.model_dump()}) + "\n"
        )
