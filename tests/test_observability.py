import time

from agentic_bi.core.observability import (
    ExecutionTimer,
    add_event,
    create_trace,
    finish_trace,
    load_trace,
    save_trace,
)


def test_trace_lifecycle():
    trace = create_trace("Which airports have the highest cancellation rates?")

    add_event(trace, "skill_selected", skill="data-analysis")

    finish_trace(trace, stop_reason="final_answer")

    assert trace.run_id
    assert trace.question == ("Which airports have the highest cancellation rates?")

    assert len(trace.events) == 1

    assert trace.events[0].event_type == "skill_selected"
    assert trace.events[0].data == {"skill": "data-analysis"}

    assert trace.finished_at is not None
    assert trace.duration_seconds is not None
    assert trace.duration_seconds >= 0

    assert trace.stop_reason == "final_answer"


def test_execution_timer_measures_elapsed_time():
    timer = ExecutionTimer()

    timer.start()
    time.sleep(0.01)
    duration = timer.stop()

    assert duration > 0


def test_trace_save_and_load(tmp_path):
    trace = create_trace("Test trace persistence")

    add_event(trace, "tool_completed", tool="test_tool", status="success")

    finish_trace(trace, stop_reason="final_answer")

    trace_path = save_trace(trace, trace_dir=tmp_path)

    loaded_trace = load_trace(trace_path)

    assert trace_path.exists()

    assert loaded_trace.run_id == trace.run_id
    assert loaded_trace.question == trace.question
    assert loaded_trace.stop_reason == "final_answer"

    assert len(loaded_trace.events) == 1

    assert loaded_trace.events[0].event_type == "tool_completed"

    assert loaded_trace.events[0].data == {"tool": "test_tool", "status": "success"}
