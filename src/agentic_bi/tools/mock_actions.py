processed_actions: set[str] = set()


def issue_customer_credit(
    customer_id: str, amount: float, reason: str, idempotency_key: str
) -> dict:
    """
    Simulate a consequential write action.

    Duplicate actions are blocked using an idempotency key.
    """

    if not customer_id.strip():
        raise ValueError("customer_id is required")

    if amount <= 0:
        raise ValueError("amount must be greater than zero")

    if not reason.strip():
        raise ValueError("reason is required")

    if not idempotency_key.strip():
        raise ValueError("idempotency_key is required")

    if idempotency_key in processed_actions:
        return {
            "status": "duplicate_blocked",
            "customer_id": customer_id,
            "amount": amount,
            "idempotency_key": idempotency_key,
        }

    processed_actions.add(idempotency_key)

    return {
        "status": "completed",
        "customer_id": customer_id,
        "amount": amount,
        "reason": reason,
        "idempotency_key": idempotency_key,
    }
