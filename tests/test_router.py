from agentic_bi.skills.router import select_skill


def test_routes_policy_question_to_knowledge_analysis():
    question = "What does Delta's policy say about refunds?"

    result = select_skill(question)

    assert result == "knowledge-analysis"


def test_routes_data_question_to_data_analysis():
    question = "Which airports have the highest cancellation rate in the flight data?"

    result = select_skill(question)

    assert result == "data-analysis"


def test_unknown_question_returns_none():
    question = "Hello, how are you?"

    result = select_skill(question)

    assert result is None


def test_keywords_do_not_match_inside_longer_words():
    # "corporate" contains "rate", "schedule" contains "rule" and
    # "update" contains "data"; none of them is a routing keyword.
    question = "Please update the corporate schedule."

    result = select_skill(question)

    assert result is None


def test_keywords_still_match_simple_inflections():
    question = "Which airports had the most delays?"

    result = select_skill(question)

    assert result == "data-analysis"
