import pytest

from agentic_bi.evaluation.common import (
    first_relevant_rank,
    hit_at_k,
    load_cases,
    load_qrels,
    reciprocal_rank,
)


def results(*chunk_ids):
    return [{"chunk_id": chunk_id} for chunk_id in chunk_ids]


def test_first_relevant_rank_is_one_based():
    assert first_relevant_rank(results("a", "b", "c"), {"b", "c"}) == 2
    assert first_relevant_rank(results("a"), {"z"}) is None
    assert first_relevant_rank(results("a"), set()) is None


@pytest.mark.parametrize(
    ("rank", "k", "expected"), [(1, 1, 1), (3, 3, 1), (4, 3, 0), (None, 5, 0)]
)
def test_hit_at_k(rank, k, expected):
    assert hit_at_k(rank, k) == expected


def test_reciprocal_rank():
    assert reciprocal_rank(1) == 1.0
    assert reciprocal_rank(4) == 0.25
    assert reciprocal_rank(None) == 0.0
    assert reciprocal_rank(6, max_rank=5) == 0.0


def test_frozen_eval_files_load():
    assert len(load_cases("agent_cases.json")) == 15
    assert len(load_cases("retrieval_cases.json")) == 10

    qrels = load_qrels()
    assert set(qrels) == {case["id"] for case in load_cases("retrieval_cases.json")}
    assert all(qrels.values())


def test_analytics_eval_checks_tool_and_listed_arguments():
    from agentic_bi.evaluation.analytics_eval import evaluate_case

    case = {
        "expected_tool": "rank_flight_performance",
        "expected_arguments": {"metric": "cancellation_rate", "only": ["JFK", "LGA"]},
    }
    history = [
        {
            "tool": "rank_flight_performance",
            "arguments": {"metric": "cancellation_rate", "only": ["LGA", "JFK"]},
        }
    ]

    assert evaluate_case(case, history) == []
    assert evaluate_case(case, [])[0].startswith("expected rank_flight_performance")

    history[0]["arguments"]["metric"] = "diversion_rate"
    assert evaluate_case(case, history) == [
        "metric: expected 'cancellation_rate', got 'diversion_rate'"
    ]


def test_analytics_cases_use_valid_arguments():
    from agentic_bi.tools.registry import TOOL_REGISTRY

    for case in load_cases("analytics_cases.json"):
        fields = TOOL_REGISTRY[case["expected_tool"]].input_model.model_fields
        assert set(case["expected_arguments"]) <= set(fields), case["id"]
