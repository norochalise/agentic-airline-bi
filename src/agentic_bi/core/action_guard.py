from collections.abc import Callable, Mapping
from typing import Any

from agentic_bi.tools.registry import TOOL_REGISTRY, ToolSpec


class ApprovalRequiredError(Exception):
    """Raised when a protected action requires explicit approval."""


def enforce_action_policy(
    tool_name: str,
    *,
    approved: bool = False,
    registry: Mapping[str, ToolSpec] = TOOL_REGISTRY,
) -> None:
    """Validate whether a tool is permitted to execute."""

    spec = registry.get(tool_name)

    if spec is None:
        raise ValueError(f"No access policy configured for tool: {tool_name}")

    if spec.access == "write" and spec.requires_approval and not approved:
        raise ApprovalRequiredError(f"Approval required for write tool: {tool_name}")


def execute_protected_action(
    tool_name: str,
    function: Callable[..., Any],
    arguments: dict[str, Any],
    *,
    approved: bool = False,
) -> Any:
    """Enforce access policy before executing a tool."""

    enforce_action_policy(tool_name, approved=approved)

    return function(**arguments)
