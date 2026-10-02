import agentic_bi.core.agent as agent_module
from agentic_bi.api.progress import progress_message
from agentic_bi.core.followup import condense_question
from conftest import FakeClient, model_response, routed_to

HISTORY = [
    {"role": "user", "content": "Which origin has the highest cancellation rate?"},
    {"role": "assistant", "content": "LGA, at 11.4%."},
]


def test_without_history_no_model_call_is_made():
    client = FakeClient([])

    assert condense_question("Top airport?", [], client=client) == "Top airport?"
    assert client.responses.requests == []


def test_follow_up_is_rewritten_with_the_conversation():
    client = FakeClient(
        [model_response("r1", output_text="What is JFK's cancellation rate?")]
    )

    rewritten = condense_question("and for JFK?", HISTORY, client=client)

    assert rewritten == "What is JFK's cancellation rate?"
    assert "LGA, at 11.4%." in client.responses.requests[0]["input"]


def test_empty_rewrite_falls_back_to_the_original():
    client = FakeClient([model_response("r1", output_text="  ")])

    assert condense_question("and for JFK?", HISTORY, client=client) == "and for JFK?"


def test_agent_answers_the_rewritten_question(monkeypatch, run_store):
    seen = []

    def classify(question, client=None):
        seen.append(question)
        return routed_to("out_of_scope")(question)

    monkeypatch.setattr(agent_module, "classify_interaction", classify)

    events = []
    client = FakeClient(
        [model_response("r1", output_text="What is JFK's cancellation rate?")]
    )

    result = agent_module.run_agent(
        "and for JFK?",
        client=client,
        store=run_store,
        history=HISTORY,
        on_event=lambda event_type, data: events.append(event_type),
    )

    assert seen == ["What is JFK's cancellation rate?"]
    assert result.goal == "What is JFK's cancellation rate?"
    assert events[:2] == ["agent_started", "question_rewritten"]


def test_a_failing_listener_does_not_stop_the_run(monkeypatch, run_store):
    monkeypatch.setattr(agent_module, "classify_interaction", routed_to("conversation"))

    def broken_listener(event_type, data):
        raise ConnectionError("browser went away")

    result = agent_module.run_agent(
        "Hi!", client=FakeClient(), store=run_store, on_event=broken_listener
    )

    assert result.stop_reason == "interaction_response"


def test_progress_messages_cover_the_user_facing_steps():
    assert progress_message("tool_started", {"tool": "search_private_knowledge"}) == (
        "Searching company documents…"
    )
    assert progress_message("interaction_classified", {"intent": "airline_data"})
    assert progress_message("tool_completed", {"status": "error"}).startswith("A step")
    assert progress_message("checkpoint_saved", {}) is None
