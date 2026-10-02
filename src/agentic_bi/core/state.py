from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AgentState:
    """
    Runtime state for a single agent execution.

    Tracks execution progress, selected workflow context,
    tool activity, observations, errors, and termination state.
    """

    goal: str

    step_count: int = 0
    tool_call_count: int = 0

    selected_skill: str | None = None
    stop_reason: str | None = None

    tool_history: list[dict[str, Any]] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable snapshot of the current agent state."""
        return asdict(self)