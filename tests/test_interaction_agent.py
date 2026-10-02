"""Agent-level regression tests for M22 interaction routing."""

from pathlib import Path

from agentic_bi.core.interaction import InteractionDecision


class FakeClient:
    """Client placeholder for requests handled before model execution."""

    pass


def test_out_of_scope_request_exits_before_agent_tool_loop(
    monkeypatch,
    tmp_path: Path,
):
    import agentic_bi.core.agent as agent_module

    monkeypatch.setattr(
        agent_module,
        "OpenAI",
        lambda: FakeClient(),
    )

    monkeypatch.setattr(
        agent_module,
        "classify_interaction",
        lambda question, client=None: InteractionDecision(
            intent="out_of_scope",
            reason="Creative writing is outside application scope.",
        ),
    )

    def fail_if_skill_router_runs(*args, **kwargs):
        raise AssertionError(
            "Skill router should not run for out-of-scope requests."
        )

    monkeypatch.setattr(
        agent_module,
        "select_skill",
        fail_if_skill_router_runs,
    )

    monkeypatch.setattr(
        agent_module,
        "save_checkpoint",
        lambda checkpoint: tmp_path / "checkpoint.json",
    )

    monkeypatch.setattr(
        agent_module,
        "save_trace",
        lambda trace: tmp_path / "trace.json",
    )

    result = agent_module.run_agent(
        "Write me a poem about Delta flights."
    )

    assert result.final_answer
    assert result.selected_skill is None
    assert result.stop_reason == "interaction_response"

    assert result.step_count == 0
    assert result.tool_call_count == 0
    assert result.knowledge_search_count == 0
    assert result.data_analysis_count == 0

    assert result.tool_history == []
    assert result.observations == []
    assert result.errors == []