"""Whole-word term matching for deterministic routing."""

import re
from functools import lru_cache


@lru_cache(maxsize=256)
def _term_pattern(term: str) -> re.Pattern[str]:
    # Allow simple inflections ("delays", "delayed") but not longer words
    # that merely contain the term ("corporate" for "rate").
    return re.compile(
        rf"(?<![a-z0-9]){re.escape(term.casefold())}(?:s|es|d|ed)?(?![a-z0-9])"
    )


def contains_term(text: str, term: str) -> bool:
    """Return True when ``term`` appears in ``text`` as a whole word or phrase."""

    return _term_pattern(term).search(text.casefold()) is not None
