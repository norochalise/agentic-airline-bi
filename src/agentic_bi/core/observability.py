from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from agentic_bi.config import TRACES_DIR
from agentic_bi.core.persistence import read_json, utc_now, write_json

DEFAULT_TRACE_DIR = TRACES_DIR


@dataclass
class TraceEvent:
    """
    One observable event during an agent run.
    """

    event_type: str
    timestamp: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTrace:
    """
    Structured trace for one complete agent run.
    """

    run_id: str
    question: str
    started_at: str

    events: list[TraceEvent] = field(default_factory=list)

    finished_at: str | None = None
    duration_seconds: float | None = None
    stop_reason: str | None = None


class ExecutionTimer:
    """
    High-resolution timer for measuring elapsed execution time.
    """

    def __init__(self) -> None:
        self._started_at: float | None = None

    def start(self) -> None:
        """Start the timer."""

        self._started_at = perf_counter()

    def stop(self) -> float:
        """
        Stop the timer and return elapsed seconds.
        """

        if self._started_at is None:
            raise RuntimeError("ExecutionTimer was stopped before it was started.")

        elapsed = perf_counter() - self._started_at

        self._started_at = None

        return elapsed


def create_trace(question: str) -> AgentTrace:
    """
    Create a new trace for an agent run.
    """

    started = utc_now()

    return AgentTrace(
        run_id=str(uuid4()), question=question, started_at=started.isoformat()
    )


def add_event(trace: AgentTrace, event_type: str, **data: Any) -> None:
    """
    Append an event to an existing trace.
    """

    trace.events.append(
        TraceEvent(event_type=event_type, timestamp=utc_now().isoformat(), data=data)
    )


def finish_trace(trace: AgentTrace, stop_reason: str | None) -> None:
    """
    Mark a trace as finished and calculate total duration.
    """

    finished = utc_now()

    started = datetime.fromisoformat(trace.started_at)

    trace.finished_at = finished.isoformat()

    trace.duration_seconds = (finished - started).total_seconds()

    trace.stop_reason = stop_reason


def save_trace(trace: AgentTrace, trace_dir: Path | None = None) -> Path:
    """
    Persist an AgentTrace as formatted JSON.

    Returns the path of the saved trace file.
    """

    target_dir = trace_dir if trace_dir is not None else DEFAULT_TRACE_DIR

    return write_json(target_dir / f"{trace.run_id}.json", asdict(trace))


def load_trace(trace_path: Path) -> AgentTrace:
    """
    Load a previously persisted trace JSON file.
    """

    data = read_json(trace_path)

    events = [
        TraceEvent(
            event_type=event["event_type"],
            timestamp=event["timestamp"],
            data=event.get("data", {}),
        )
        for event in data.get("events", [])
    ]

    return AgentTrace(
        run_id=data["run_id"],
        question=data["question"],
        started_at=data["started_at"],
        events=events,
        finished_at=data.get("finished_at"),
        duration_seconds=data.get("duration_seconds"),
        stop_reason=data.get("stop_reason"),
    )
