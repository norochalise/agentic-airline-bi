"""Shared API clients, created once per process."""

from functools import lru_cache

from openai import OpenAI


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    """Return the process-wide OpenAI client (it pools HTTP connections)."""

    return OpenAI()
