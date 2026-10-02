from agentic_bi.skills.registry import SKILL_REGISTRY


def select_skill(goal: str) -> str | None:
    """
    Select a registered skill using weighted deterministic routing.

    Phrase matches receive greater weight than individual keyword
    matches. Ambiguous ties are left unresolved.
    """

    normalized_goal = goal.lower()

    scores: dict[str, int] = {}

    for skill_name, config in SKILL_REGISTRY.items():
        keyword_score = sum(
            keyword in normalized_goal
            for keyword in config["keywords"]
        )

        phrase_score = sum(
            3
            for phrase in config["phrases"]
            if phrase in normalized_goal
        )

        scores[skill_name] = keyword_score + phrase_score

    best_score = max(scores.values())

    if best_score == 0:
        return None

    winners = [
        skill_name
        for skill_name, score in scores.items()
        if score == best_score
    ]

    if len(winners) != 1:
        return None

    return winners[0]