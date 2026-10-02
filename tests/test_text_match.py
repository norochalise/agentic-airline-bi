import pytest

from agentic_bi.core.text_match import contains_term


@pytest.mark.parametrize(
    ("text", "term"),
    [
        ("How is the RAG pipeline built?", "rag"),
        ("Show delays by airport", "delay"),
        ("Flights were delayed", "delay"),
        ("What is in the 10-K?", "10-k"),
        ("According to the Customer Service Plan, ...", "customer service plan"),
    ],
)
def test_contains_term_matches_whole_words(text, term):
    assert contains_term(text, term)


@pytest.mark.parametrize(
    ("text", "term"),
    [
        ("What is the average delay?", "rag"),
        ("Leverage and storage costs", "rag"),
        ("A corporate account", "rate"),
        ("The flight schedule", "rule"),
        ("Please update it", "data"),
    ],
)
def test_contains_term_ignores_substrings_of_other_words(text, term):
    assert not contains_term(text, term)
