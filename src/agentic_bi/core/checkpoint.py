import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentic_bi.config import CHECKPOINTS_DIR
from agentic_bi.core.state import AgentState

DEFAULT_CHECKPOINT_DIR = CHECKPOINTS_DIR


@dataclass
class AgentCheckpoint:
    """
    Serializable snapshot of an agent's execution state.
    """

    run_id: str
    checkpoint_id: str
    created_at: str
    state: dict[str, Any]


def utc_now_iso() -> str:
    """
    Return the current UTC time as an ISO-8601 string.
    """

    return datetime.now(UTC).isoformat()


def create_checkpoint(
    run_id: str, checkpoint_id: str, state: AgentState
) -> AgentCheckpoint:
    """
    Create an in-memory checkpoint from the current AgentState.
    """

    return AgentCheckpoint(
        run_id=run_id,
        checkpoint_id=checkpoint_id,
        created_at=utc_now_iso(),
        state=state.to_dict(),
    )


def checkpoint_to_dict(checkpoint: AgentCheckpoint) -> dict[str, Any]:
    """
    Convert an AgentCheckpoint into a JSON-serializable dictionary.
    """

    return {
        "run_id": checkpoint.run_id,
        "checkpoint_id": checkpoint.checkpoint_id,
        "created_at": checkpoint.created_at,
        "state": checkpoint.state,
    }


def save_checkpoint(
    checkpoint: AgentCheckpoint, checkpoint_dir: Path | None = None
) -> Path:
    """
    Persist a checkpoint to disk.

    Checkpoints are grouped by agent run ID.
    """

    root_dir = checkpoint_dir if checkpoint_dir is not None else DEFAULT_CHECKPOINT_DIR

    run_dir = root_dir / checkpoint.run_id

    run_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_path = run_dir / f"{checkpoint.checkpoint_id}.json"

    with checkpoint_path.open("w", encoding="utf-8") as file:
        json.dump(
            checkpoint_to_dict(checkpoint),
            file,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    return checkpoint_path


def load_checkpoint(checkpoint_path: Path) -> AgentCheckpoint:
    """
    Load a previously persisted checkpoint.
    """

    with checkpoint_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return AgentCheckpoint(
        run_id=data["run_id"],
        checkpoint_id=data["checkpoint_id"],
        created_at=data["created_at"],
        state=data["state"],
    )


def restore_agent_state(checkpoint: AgentCheckpoint) -> AgentState:
    """
    Reconstruct AgentState from a checkpoint snapshot.

    This restores our application-level state. It does not
    automatically restore an external model/API conversation.
    """

    state_data = checkpoint.state

    return AgentState(
        goal=state_data["goal"],
        step_count=state_data.get("step_count", 0),
        tool_call_count=state_data.get("tool_call_count", 0),
        selected_skill=state_data.get("selected_skill"),
        stop_reason=state_data.get("stop_reason"),
        tool_history=state_data.get("tool_history", []),
        observations=state_data.get("observations", []),
        errors=state_data.get("errors", []),
    )
