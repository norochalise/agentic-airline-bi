"""Plain-language progress messages for the streaming endpoint."""

from typing import Any

INTENT_MESSAGES = {
    "airline_data": "Planning a flight-data analysis…",
    "airline_knowledge": "Looking for the right documents…",
    "current_airline_info": "Checking official airline and government websites…",
}

TOOL_MESSAGES = {
    "search_private_knowledge": "Searching company documents…",
    "search_official_web": "Searching official websites…",
    "analyze_top_origin_cancellation_rates": "Analyzing flight data…",
    "rank_flight_performance": "Analyzing flight data…",
    "analyze_delay_causes": "Breaking down delay causes…",
}


def progress_message(event_type: str, data: dict[str, Any]) -> str | None:
    """The status line to show for a trace event, or None to skip it."""

    if event_type == "agent_started":
        return "Reading the question…"

    if event_type == "question_rewritten":
        return f"Follow-up understood as: {data.get('standalone', '')}"

    if event_type == "interaction_classified":
        return INTENT_MESSAGES.get(data.get("intent"), "Writing a reply…")

    if event_type == "tool_started":
        return TOOL_MESSAGES.get(data.get("tool"), "Running a tool…")

    if event_type == "tool_completed":
        if data.get("status") == "success":
            return "Writing the answer…"
        return "A step failed; adjusting…"

    return None
