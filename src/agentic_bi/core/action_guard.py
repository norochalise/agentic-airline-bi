from collections.abc import Callable
from typing import Any

TOOL_ACCESS_POLICIES = {
    "search_private_knowledge": {"access": "read", "requires_approval": False},
    "analyze_top_origin_cancellation_rates": {
        "access": "read",
        "requires_approval": False,
    },
    "search_official_web": {"access": "read", "requires_approval": False},
    "issue_customer_credit": {"access": "write", "requires_approval": True},
}


class ApprovalRequiredError(Exception):
    """Raised when a protected action requires explicit approval."""


def enforce_action_policy(tool_name: str, *, approved: bool = False) -> None:
    """Validate whether a tool is permitted to execute."""

    policy = TOOL_ACCESS_POLICIES.get(tool_name)

    if policy is None:
        raise ValueError(f"No access policy configured for tool: {tool_name}")

    if policy["access"] == "write" and policy["requires_approval"] and not approved:
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
