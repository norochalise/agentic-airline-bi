"""Interaction routing and scope control for the Agentic BI application."""
from dotenv import load_dotenv
import json
import os
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field
load_dotenv()

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
- Questions about airline policies, contracts, customer commitments,
  financial documents, regulatory documents, or other information that
  should be answered from the application's existing document knowledge base.
- Examples:
  "What does the contract say about refunds?"
  "What does the customer service plan say about delays?"

current_airline_info
- Airline questions that explicitly require current, live, latest, recent,
  today, or up-to-date information from the web.
- Examples:
  "What is the current baggage policy?"
  "What does the airline website say about refunds today?"
- This intent identifies the need for current information.
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
6. Use current_airline_info only when current/live web information is
   actually required.
7. Return only the requested structured classification.
"""


def classify_interaction(
    question: str,
    client: OpenAI | None = None,
) -> InteractionDecision:
    """Classify a user request before it enters the main agent."""

    question = question.strip()

    if not question:
        raise ValueError("Question must not be empty.")

    if client is None:
        client = OpenAI()

    response = client.responses.create(
        model=os.environ["OPENAI_MODEL"],
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
                        "reason": {
                            "type": "string",
                        },
                    },
                    "required": [
                        "intent",
                        "reason",
                    ],
                    "additionalProperties": False,
                },
            }
        },
    )

    data = json.loads(response.output_text)

    return InteractionDecision.model_validate(data)