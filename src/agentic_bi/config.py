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
