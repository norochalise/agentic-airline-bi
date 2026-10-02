import pytest

from agentic_bi.core.action_guard import (
    ApprovalRequiredError,
    enforce_action_policy,
    execute_protected_action,
)


def test_read_action_does_not_require_approval():
    enforce_action_policy(
        "search_private_knowledge",
        approved=False,
    )


def test_write_action_requires_approval():
    with pytest.raises(ApprovalRequiredError):
        enforce_action_policy(
            "issue_customer_credit",
            approved=False,
        )


def test_approved_write_action_can_execute():
    def fake_write_action(
        customer_id: str,
        amount: float,
    ) -> dict:
        return {
            "customer_id": customer_id,
            "amount": amount,
            "status": "completed",
        }

    result = execute_protected_action(
        tool_name="issue_customer_credit",
        function=fake_write_action,
        arguments={
            "customer_id": "C-105",
            "amount": 75.0,
        },
        approved=True,
    )

    assert result == {
        "customer_id": "C-105",
        "amount": 75.0,
        "status": "completed",
    }


def test_unapproved_write_action_is_not_executed():
    call_count = 0

    def fake_write_action() -> None:
        nonlocal call_count
        call_count += 1

    with pytest.raises(ApprovalRequiredError):
        execute_protected_action(
            tool_name="issue_customer_credit",
            function=fake_write_action,
            arguments={},
            approved=False,
        )

    assert call_count == 0


def test_unknown_tool_is_rejected():
    with pytest.raises(ValueError):
        enforce_action_policy(
            "unknown_tool",
            approved=True,
        )