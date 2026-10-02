"""Current Delta information synthesis using Exa-retrieved official sources."""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from agentic_bi.tools.delta_official_web import (
    search_delta_official_web,
)


load_dotenv()


def _build_evidence_text(
    search_result: dict[str, Any],
) -> str:
    """Convert validated Exa results into bounded evidence text."""

    sections: list[str] = []

    for index, result in enumerate(
        search_result.get("results", []),
        start=1,
    ):
        title = result.get("title") or "Delta"
        url = result.get("url") or ""

        highlights = result.get(
            "highlights",
            [],
        )

        highlight_text = "\n\n".join(
            str(item)
            for item in highlights
            if str(item).strip()
        )

        sections.append(
            (
                f"SOURCE {index}\n"
                f"Title: {title}\n"
                f"URL: {url}\n"
                f"Evidence:\n{highlight_text}"
            )
        )

    return "\n\n---\n\n".join(
        sections
    )


def answer_current_delta_question(
    question: str,
    client: OpenAI | None = None,
    num_results: int = 3,
) -> dict[str, Any]:
    """
    Answer a current Delta question using only Exa-retrieved
    official Delta web evidence.
    """

    question = question.strip()

    if not question:
        raise ValueError(
            "Question must not be empty."
        )

    search_result = search_delta_official_web(
        query=question,
        num_results=num_results,
    )

    results = search_result.get(
        "results",
        [],
    )

    if not results:
        return {
            "answer": (
                "I could not verify this from the current "
                "official Delta website."
            ),
            "sources": [],
            "source_type": "live_official_web",
            "provider": "exa",
        }

    evidence_text = _build_evidence_text(
        search_result
    )

    if client is None:
        client = OpenAI()

    response = client.responses.create(
        model=os.environ["OPENAI_MODEL"],
        instructions=(
            "You are answering a current airline-information question. "
            "Use only the evidence supplied in the input. "
            "Do not add facts from memory or outside knowledge. "
            "If the evidence is incomplete, explicitly say so. "
            "Keep the answer concise and factual. "
            "Do not invent citations, URLs, dates, fees, rules, "
            "exceptions, or policy details. "
            "Do not mention the retrieval provider or model provider. "
            "Do not include a separate source list in the answer text "
            "because structured sources are returned separately."
        ),
        input=(
            f"QUESTION:\n{question}\n\n"
            f"OFFICIAL DELTA WEB EVIDENCE:\n"
            f"{evidence_text}"
        ),
    )

    sources = [
        {
            "title": result.get(
                "title",
                "Delta",
            ),
            "url": result.get(
                "url",
                "",
            ),
        }
        for result in results
        if result.get("url")
    ]

    return {
        "answer": response.output_text.strip(),
        "sources": sources,
        "source_type": "live_official_web",
        "provider": "exa",
    }