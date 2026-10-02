"""Keep the Docker image and CI in step with the code."""

from agentic_bi.config import EMBEDDING_MODEL, PROJECT_ROOT, RERANKER_MODEL


def test_docker_image_bakes_the_configured_models():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert EMBEDDING_MODEL in dockerfile
    assert RERANKER_MODEL in dockerfile


def test_docker_context_keeps_secrets_and_run_output_out():
    ignored = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8").split()

    for entry in (".env", ".venv", ".git", "data/traces", "data/checkpoints"):
        assert entry in ignored


def test_ci_runs_lint_format_and_tests():
    workflow = (PROJECT_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    for command in ("uv sync --frozen", "ruff check", "ruff format --check", "pytest"):
        assert command in workflow
