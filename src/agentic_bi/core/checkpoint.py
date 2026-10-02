from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agentic_bi.config import CHECKPOINTS_DIR
from agentic_bi.core.persistence import read_json, utc_now_iso, write_json
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


def save_checkpoint(
    checkpoint: AgentCheckpoint, checkpoint_dir: Path | None = None
) -> Path:
    """
    Persist a checkpoint to disk.

    Checkpoints are grouped by agent run ID.
    """

    root_dir = checkpoint_dir if checkpoint_dir is not None else DEFAULT_CHECKPOINT_DIR

    return write_json(
        root_dir / checkpoint.run_id / f"{checkpoint.checkpoint_id}.json",
        asdict(checkpoint),
    )


def load_checkpoint(checkpoint_path: Path) -> AgentCheckpoint:
    """
    Load a previously persisted checkpoint.
    """

    return AgentCheckpoint(**read_json(checkpoint_path))


def restore_agent_state(checkpoint: AgentCheckpoint) -> AgentState:
    """
    Reconstruct AgentState from a checkpoint snapshot.

    This restores our application-level state. It does not
    automatically restore an external model/API conversation.
    """

    return AgentState(**checkpoint.state)
