from agentic_bi.core.checkpoint import (
    create_checkpoint,
    load_checkpoint,
    restore_agent_state,
    save_checkpoint,
)
from agentic_bi.core.state import AgentState


def test_checkpoint_save_load_and_restore(tmp_path):
    state = AgentState(
        goal="Analyze Delta cancellation rates",
        step_count=2,
        tool_call_count=1,
        selected_skill="data-analysis",
        stop_reason=None,
        tool_history=[{"tool": "analyze_top_origin_cancellation_rates"}],
        observations=[{"status": "success"}],
        errors=[],
    )

    checkpoint = create_checkpoint(
        run_id="test-run-001", checkpoint_id="step_2", state=state
    )

    checkpoint_path = save_checkpoint(checkpoint, checkpoint_dir=tmp_path)

    loaded_checkpoint = load_checkpoint(checkpoint_path)

    restored_state = restore_agent_state(loaded_checkpoint)

    assert checkpoint_path.exists()

    assert loaded_checkpoint.run_id == "test-run-001"
    assert loaded_checkpoint.checkpoint_id == "step_2"

    assert restored_state.goal == ("Analyze Delta cancellation rates")
    assert restored_state.step_count == 2
    assert restored_state.tool_call_count == 1
    assert restored_state.selected_skill == "data-analysis"

    assert restored_state.tool_history == [
        {"tool": "analyze_top_origin_cancellation_rates"}
    ]

    assert restored_state.observations == [{"status": "success"}]

    assert restored_state.errors == []
