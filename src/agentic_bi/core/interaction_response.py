"""Bounded responses for non-BI interaction intents."""

from agentic_bi.core.interaction import InteractionIntent
from agentic_bi.core.text_match import contains_term


APP_NAME = "Airline Intelligence Assistant"
PROJECT_NAME = "Agentic Business Intelligence"
BUILDER_NAME = "Noro Insight"


def build_interaction_response(
    intent: InteractionIntent,
    question: str,
) -> str | None:
    """Return a bounded response when the main BI agent is not required."""

    if intent == "conversation":
        return (
            f"Hi! I'm the {APP_NAME}, built as part of the "
            f"{PROJECT_NAME} project by {BUILDER_NAME}. "
            "You can ask me about airline flight data, policies, "
            "contracts, customer commitments, and current official "
            "airline information."
        )

    if intent == "app_info":
        return _build_app_info_response(question)

    if intent == "out_of_scope":
        return (
            f"I'm the {APP_NAME}, so I stay focused on airline "
            "business-intelligence questions. I can help analyze the "
            "available flight data, answer questions from the airline "
            "document knowledge base, and look up current official "
            "airline information."
        )

    if intent == "current_airline_info":
        # Handled by the dedicated Exa-backed official-web path in agent.py.
        return None

    # airline_data and airline_knowledge continue to the main agent.
    return None


def _build_app_info_response(question: str) -> str:
    """Answer common questions about this application."""

    if any(
        contains_term(question, phrase)
        for phrase in (
            "who built",
            "who made",
            "who created",
            "who developed",
            "who is your creator",
        )
    ):
        return (
            f"The {APP_NAME} is part of the {PROJECT_NAME} "
            f"portfolio project built by {BUILDER_NAME}."
        )

    if any(
        contains_term(question, phrase)
        for phrase in (
            "what can you do",
            "what do you do",
            "your capabilities",
            "what are your capabilities",
            "how can you help",
        )
    ):
        return (
            "I can analyze the available airline flight dataset, "
            "answer grounded questions from the document knowledge base, "
            "and retrieve current information from official airline web "
            "sources. The system routes questions to the appropriate "
            "analysis path, validates tool inputs and outputs, applies "
            "execution guards, and records execution traces."
        )

    if any(
        contains_term(question, phrase)
        for phrase in (
            "how were you built",
            "how are you built",
            "how was this built",
            "how does this work",
            "architecture",
            "rag",
            "tools",
            "implementation",
        )
    ):
        return (
            "This application is built as a bounded agentic business-"
            "intelligence system. It uses interaction routing and skill "
            "routing to direct questions to structured flight-data "
            "analysis, a private-document RAG pipeline, or trusted "
            "official-web retrieval for current information. The system "
            "also includes validated tool calling, bounded execution, "
            "retry policies, safety guards, local embeddings and FAISS "
            "retrieval, reranking, tracing, checkpointing, evaluation, "
            "and a FastAPI web interface."
        )

    return (
        f"I'm the {APP_NAME}, part of the {PROJECT_NAME} "
        f"portfolio project by {BUILDER_NAME}. I'm designed to analyze "
        "airline data, answer grounded questions from the available "
        "document knowledge base, and retrieve current information from "
        "official airline web sources."
    )
