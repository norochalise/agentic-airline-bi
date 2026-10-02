from dataclasses import dataclass, field
from typing import Any


@dataclass
class FailureRecord:
    """
    Structured description of one evaluation failure.

    A single agent run can produce more than one failure.
    For example, the agent may select the wrong tool and
    therefore also produce the wrong arguments.
    """

    category: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def classify_failures(
    *,
    skill_ok: bool,
    tool_ok: bool,
    argument_ok: bool,
    stop_ok: bool,
    errors_ok: bool,
    answer_ok: bool,
    expected_skill: str | None = None,
    actual_skill: str | None = None,
    expected_tool: str | None = None,
    used_tools: list[str] | None = None,
    expected_arguments: dict[str, Any] | None = None,
    actual_arguments: dict[str, Any] | None = None,
    expected_stop_reason: str | None = None,
    actual_stop_reason: str | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> list[FailureRecord]:
    """
    Convert deterministic evaluation checks into structured
    failure categories.

    This function does not call an LLM. Classification is based
    entirely on the observed AgentResult and evaluation checks.
    """

    failures: list[FailureRecord] = []

    used_tools = used_tools or []
    errors = errors or []

    # ---------------------------------------------------------
    # 1. ROUTING FAILURE
    # ---------------------------------------------------------

    if not skill_ok:
        failures.append(
            FailureRecord(
                category="routing_failure",
                message="The agent selected the wrong skill.",
                details={
                    "expected_skill": expected_skill,
                    "actual_skill": actual_skill,
                },
            )
        )

    # ---------------------------------------------------------
    # 2. TOOL-SELECTION FAILURE
    # ---------------------------------------------------------

    if not tool_ok:
        failures.append(
            FailureRecord(
                category="tool_selection_failure",
                message="The expected tool was not successfully used.",
                details={"expected_tool": expected_tool, "used_tools": used_tools},
            )
        )

    # ---------------------------------------------------------
    # 3. ARGUMENT FAILURE
    # ---------------------------------------------------------

    if not argument_ok:
        failures.append(
            FailureRecord(
                category="argument_failure",
                message=(
                    "The expected tool arguments did not match the observed arguments."
                ),
                details={
                    "expected_arguments": expected_arguments,
                    "actual_arguments": actual_arguments,
                },
            )
        )

    # ---------------------------------------------------------
    # 4. TOOL-EXECUTION FAILURE
    # ---------------------------------------------------------

    if not errors_ok:
        failures.append(
            FailureRecord(
                category="tool_execution_failure",
                message=(
                    "The agent recorded one or more execution or validation errors."
                ),
                details={"errors": errors},
            )
        )

    # ---------------------------------------------------------
    # 5. TERMINATION / GUARD FAILURE
    # ---------------------------------------------------------

    if not stop_ok:
        guard_stop_reasons = {
            "tool_call_budget_exceeded",
            "blocked_unknown_tool",
            "repeated_tool_call",
            "knowledge_search_budget_exceeded",
            "data_analysis_budget_exceeded",
            "max_steps_reached",
        }

        if actual_stop_reason in guard_stop_reasons:
            category = "guard_triggered"
            message = (
                "A safety or execution guard stopped the agent "
                "before the expected termination."
            )

        else:
            category = "termination_failure"
            message = "The agent terminated with an unexpected stop reason."

        failures.append(
            FailureRecord(
                category=category,
                message=message,
                details={
                    "expected_stop_reason": expected_stop_reason,
                    "actual_stop_reason": actual_stop_reason,
                },
            )
        )

    # ---------------------------------------------------------
    # 6. ANSWER FAILURE
    # ---------------------------------------------------------

    if not answer_ok:
        failures.append(
            FailureRecord(
                category="answer_failure",
                message=(
                    "The final answer did not satisfy the "
                    "deterministic answer requirements."
                ),
            )
        )

    return failures


def summarize_failure_categories(failures: list[FailureRecord]) -> dict[str, int]:
    """
    Count failures by category.

    Useful for aggregate evaluation reports.
    """

    summary: dict[str, int] = {}

    for failure in failures:
        summary[failure.category] = summary.get(failure.category, 0) + 1

    return summary
