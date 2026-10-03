"""Central configuration: project paths, environment settings and constants.

Every module takes its paths and tuning values from here, so the project
root is resolved once and `.env` is loaded once.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# src/agentic_bi/config.py -> repository root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

PACKAGE_DIR = PROJECT_ROOT / "src" / "agentic_bi"
FRONTEND_DIR = PACKAGE_DIR / "frontend"
SKILLS_DIR = PROJECT_ROOT / "skills"
EVALS_DIR = PROJECT_ROOT / "evals"

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw" / "delta_small_pack"
DOCUMENTS_DIR = RAW_DATA_DIR / "documents"
FLIGHT_DATA_PATH = RAW_DATA_DIR / "flights" / "delta_marketing_flights_2026_07.csv"

RAG_CACHE_DIR = DATA_DIR / "processed" / "rag"
FAISS_INDEX_PATH = RAG_CACHE_DIR / "delta_knowledge.faiss"

TRACES_DIR = DATA_DIR / "traces"
CHECKPOINTS_DIR = DATA_DIR / "checkpoints"
FEEDBACK_PATH = DATA_DIR / "feedback" / "feedback.jsonl"


def project_relative(path: Path) -> str:
    """Return `path` relative to the project root when it lies inside it."""

    resolved = path.resolve()

    if resolved.is_relative_to(PROJECT_ROOT):
        return resolved.relative_to(PROJECT_ROOT).as_posix()

    return str(path)


# ---------------------------------------------------------------------------
# Environment settings
# ---------------------------------------------------------------------------

# Values already set in the environment take precedence over `.env`.
load_dotenv(PROJECT_ROOT / ".env")


class ConfigError(RuntimeError):
    """A required setting is missing."""


REQUIRED_SETTINGS = ("OPENAI_API_KEY", "OPENAI_MODEL")
OPTIONAL_SETTINGS = ("EXA_API_KEY",)


def _require(name: str) -> str:
    # Read at call time so tests and deployments can change the environment.
    value = os.getenv(name, "").strip()

    if not value:
        raise ConfigError(
            f"{name} is not configured. Set it in .env (see .env.example)."
        )

    return value


def openai_model() -> str:
    """Chat model used for every LLM call."""

    return _require("OPENAI_MODEL")


def exa_api_key() -> str:
    """API key for the official-web search."""

    return _require("EXA_API_KEY")


def tool_transport() -> str:
    """How the flight-data tool runs: in this process, or through MCP."""

    value = os.getenv("TOOL_TRANSPORT", "inprocess").strip().casefold()

    if value not in ("inprocess", "mcp"):
        raise ConfigError(
            f"TOOL_TRANSPORT must be 'inprocess' or 'mcp', not {value!r}."
        )

    return value


def persist_runs() -> bool:
    """Whether traces and checkpoints are written to disk."""

    return os.getenv("PERSIST_RUNS", "true").strip().casefold() not in (
        "0",
        "false",
        "no",
        "off",
    )


def max_saved_runs() -> int:
    """How many runs' traces and checkpoints to keep on disk."""

    value = os.getenv("MAX_SAVED_RUNS", "500").strip()

    try:
        limit = int(value)
    except ValueError:
        message = f"MAX_SAVED_RUNS must be an integer, not {value!r}."
        raise ConfigError(message) from None

    if limit < 1:
        raise ConfigError("MAX_SAVED_RUNS must be at least 1.")

    return limit


def _non_negative_int(name: str, default: str) -> int:
    value = os.getenv(name, default).strip()

    try:
        number = int(value)
    except ValueError:
        raise ConfigError(f"{name} must be an integer, not {value!r}.") from None

    if number < 0:
        raise ConfigError(f"{name} must be 0 (off) or more.")

    return number


def ask_rate_limit() -> int:
    """Questions per minute one client may ask; 0 turns the limit off."""

    return _non_negative_int("ASK_RATE_LIMIT", "10")


def ask_daily_limit() -> int:
    """Questions per day across all clients; 0 (the default) means no cap."""

    return _non_negative_int("ASK_DAILY_LIMIT", "0")


def _price(name: str) -> float | None:
    value = os.getenv(name, "").strip()

    if not value:
        return None

    try:
        price = float(value)
    except ValueError:
        raise ConfigError(f"{name} must be a number, not {value!r}.") from None

    if price < 0:
        raise ConfigError(f"{name} must not be negative.")

    return price


def openai_prices() -> tuple[float, float, float] | None:
    """
    USD per million (input, cached input, output) tokens for OPENAI_MODEL,
    or None when the input or output price is not set. Cached input
    defaults to the input price.
    """

    input_price = _price("OPENAI_INPUT_PRICE_PER_M")
    cached_price = _price("OPENAI_CACHED_INPUT_PRICE_PER_M")
    output_price = _price("OPENAI_OUTPUT_PRICE_PER_M")

    if input_price is None or output_price is None:
        return None

    return (
        input_price,
        cached_price if cached_price is not None else input_price,
        output_price,
    )


def warm_up_on_startup() -> bool:
    """Whether the API loads models and data before serving requests."""

    return os.getenv("WARM_UP_ON_STARTUP", "true").strip().casefold() not in (
        "0",
        "false",
        "no",
        "off",
    )


def missing_settings(names: tuple[str, ...] = REQUIRED_SETTINGS) -> list[str]:
    """Return the names in `names` that are not set."""

    return [name for name in names if not os.getenv(name, "").strip()]


def validate_settings() -> None:
    """Fail fast at startup when a required setting is missing."""

    missing = missing_settings()

    if missing:
        raise ConfigError(
            f"Missing required settings: {', '.join(missing)}. "
            "Set them in .env (see .env.example)."
        )

    # Malformed optional numbers should also fail at startup, not per request.
    max_saved_runs()
    ask_rate_limit()
    ask_daily_limit()
    openai_prices()


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"

# FAISS returns this many candidates; the cross-encoder keeps the best few.
RETRIEVAL_CANDIDATE_K = 15
RETRIEVAL_TOP_K = 5


# ---------------------------------------------------------------------------
# Agent limits
# ---------------------------------------------------------------------------

MAX_STEPS = 4
MAX_TOOL_CALLS = 4
MAX_KNOWLEDGE_SEARCHES = 2
MAX_DATA_ANALYSIS_CALLS = 1
MAX_WEB_SEARCHES = 1
