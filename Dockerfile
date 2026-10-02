# syntax=docker/dockerfile:1

# Agentic BI: API + chat UI. Build: docker build -t agentic-bi .
# Run with your keys: docker compose up  (reads .env)

FROM python:3.13-slim

# Same uv version as the lock file was made with.
COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    HF_HOME=/app/.cache/huggingface \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1. Dependencies only: this layer is reused until pyproject.toml or
#    uv.lock change. On Linux, torch comes from the CPU-only index.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# 2. Bake the local embedding and reranker models into the image, so the
#    container starts without downloading anything. Keep these names in
#    sync with EMBEDDING_MODEL / RERANKER_MODEL in config.py (a test checks).
RUN uv run --no-sync python -c "\
from sentence_transformers import CrossEncoder, SentenceTransformer; \
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L6-v2')"

# 3. Application code, skills, frozen evals and the bundled data + index.
COPY src ./src
COPY skills ./skills
COPY evals ./evals
COPY data/raw ./data/raw
COPY data/processed ./data/processed
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Run as an unprivileged user; only the run logs and feedback are writable.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p data/traces data/checkpoints data/feedback \
    && chown -R app:app data/traces data/checkpoints data/feedback
USER app

ENV PATH="/app/.venv/bin:$PATH" \
    HF_HUB_OFFLINE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["abi-serve", "--host", "0.0.0.0", "--port", "8000"]
