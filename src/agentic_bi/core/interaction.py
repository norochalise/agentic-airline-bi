"""Interaction routing and scope control for the Agentic BI application."""

import json
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field

from agentic_bi.config import openai_model
from agentic_bi.core.clients import get_openai_client

InteractionIntent = Literal[
    "conversation",
    "app_info",
    "airline_data",
    "airline_knowledge",
    "current_airline_info",
    "out_of_scope",
]


class InteractionDecision(BaseModel):
    """Structured decision produced by the interaction router."""

    intent: InteractionIntent

    reason: str = Field(
        description="Short explanation of why this intent was selected."
    )


ROUTER_INSTRUCTIONS = """
You are the scope and interaction router for an Airline Intelligence
Assistant.

Classify the user's request into exactly one intent.

LOCAL KNOWLEDGE (what the application can answer without the web)

Documents:
- Delta 2025 annual report (Form 10-K): strategy, financials, fleet,
  workforce, business and operational risks.
- Delta Customer Service Plan: customer commitments for delays,
  cancellations, refunds, tarmac delays, accessibility, baggage handling.
- Delta Domestic Contract of Carriage (plain-language, August 2026):
  domestic carriage rules, refunds, schedule changes, denied boarding.
- U.S. DOT Air Travel Consumer Report (September 2026, July 2026 data):
  on-time performance, cancellations, complaints, mishandled baggage.

Structured data:
- Delta-marketed domestic flights for July 2026: delays, cancellations,
  airports, routes, and delay causes.

INTENTS

conversation
- Greetings, thanks, goodbyes, and other lightweight social interaction.
- Examples: "hello", "good morning", "thanks".

app_info
- Questions about this application itself.
- Includes who built it, what it can do, how it works, its architecture,
  tools, data sources, RAG system, agent design, or implementation.
- Examples:
  "Who built you?"
  "What can you do?"
  "How were you built?"
  "How does your RAG system work?"

airline_data
- Questions that should be answered by analyzing the available structured
  airline flight dataset.
- Examples:
  "Which origin has the highest cancellation rate?"
  "Show the airports with the most cancellations."

airline_knowledge
- Questions whose topic is covered by the LOCAL KNOWLEDGE documents:
  contract rules, customer commitments, Delta's annual report, or the
  DOT consumer report.
- Examples:
  "What does the contract say about refunds?"
  "What does the customer service plan say about delays?"

current_airline_info
- Airline questions that must be answered from official live web sources
  (Delta and U.S. government sites such as DOT, FAA, and BTS).
- Use it when ANY of these is true:
  1. Freshness: the user asks for current, live, latest, recent, today,
     now, or up-to-date information.
  2. Not covered locally: the topic is outside LOCAL KNOWLEDGE, such as
     bag fees, pet travel, SkyMiles, seat selection, travel waivers,
     flight status, airline news, or current DOT/FAA rules.
  3. Explicit request: the user asks to check the website or search
     the web.
- Examples:
  "What is the current baggage policy?"
  "Can I bring my dog in the cabin on Delta?"
  "How do SkyMiles upgrades work?"
  "What are the DOT rules for automatic refunds?"
  "Check delta.com for the refund policy."
- This intent identifies the need for live web information.
- It does not perform web search itself.

out_of_scope
- Requests unrelated to this Airline Intelligence Assistant.
- Examples include creative writing, general programming help, recipes,
  unrelated news, general trivia, entertainment, and unrelated research.
- Example:
  "Write me a poem."
  "Tell me a story."
  "Teach me Python."
  "Give me a dinner recipe."

IMPORTANT RULES

1. Classify by the user's underlying intent, not by isolated keywords.
2. A request does not become airline_data merely because it mentions an
   airport or airline.
3. Creative or unrelated requests remain out_of_scope even if they contain
   airline vocabulary.
   Example: "Write a poem about Delta flights" is out_of_scope.
4. Questions about how THIS application was built are app_info.
5. Questions about how to build some unrelated application are out_of_scope.
6. Use current_airline_info only when one of its three conditions holds.
7. If the user names a LOCAL KNOWLEDGE document (for example "according
   to the contract", "the 10-K", "the customer service plan", "the DOT
   report"), choose airline_knowledge, even if the question also asks
   whether it is still current. The main agent can verify it on the web.
8. Questions that ask for metrics computed from the flight dataset are
   airline_data, never current_airline_info.
9. Return only the requested structured classification.
"""


def classify_interaction(
    question: str, client: OpenAI | None = None
) -> InteractionDecision:
    """Classify a user request before it enters the main agent."""

    question = question.strip()

    if not question:
        raise ValueError("Question must not be empty.")

    if client is None:
        client = get_openai_client()

    response = client.responses.create(
        model=openai_model(),
        instructions=ROUTER_INSTRUCTIONS,
        input=question,
        text={
            "format": {
                "type": "json_schema",
                "name": "interaction_decision",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "intent": {
                            "type": "string",
                            "enum": [
                                "conversation",
                                "app_info",
                                "airline_data",
                                "airline_knowledge",
                                "current_airline_info",
                                "out_of_scope",
                            ],
                        },
                        "reason": {"type": "string"},
                    },
                    "required": ["intent", "reason"],
                    "additionalProperties": False,
                },
            }
        },
    )

    data = json.loads(response.output_text)

    return InteractionDecision.model_validate(data)
