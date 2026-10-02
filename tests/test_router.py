from agentic_bi.skills.router import select_skill


def test_routes_policy_question_to_knowledge_analysis():
    question = "What does Delta's policy say about refunds?"

    result = select_skill(question)

    assert result == "knowledge-analysis"


def test_routes_data_question_to_data_analysis():
    question = (
        "Which airports have the highest "
        "cancellation rate in the flight data?"
    )

    result = select_skill(question)

    assert result == "data-analysis"


def test_unknown_question_returns_none():
    question = "Hello, how are you?"

    result = select_skill(question)

    assert result is None