"""Agent-level regression tests for M22 interaction routing."""

import agentic_bi.core.agent as agent_module
from conftest import FakeClient, routed_to


def test_out_of_scope_request_exits_before_agent_tool_loop(monkeypatch, run_store):
    monkeypatch.setattr(agent_module, "classify_interaction", routed_to("out_of_scope"))

    def fail_if_skill_router_runs(*args, **kwargs):
        raise AssertionError("Skill router should not run for out-of-scope requests.")

    monkeypatch.setattr(agent_module, "select_skill", fail_if_skill_router_runs)

    result = agent_module.run_agent(
        "Write me a poem about Delta flights.", client=FakeClient(), store=run_store
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

    # The run is still recorded: one final checkpoint and one trace.
    assert [c.checkpoint_id for c in run_store.checkpoints] == ["final"]
    assert len(run_store.traces) == 1
