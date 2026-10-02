import pytest

from agentic_bi import config


def test_paths_resolve_inside_the_repository():
    assert (config.PROJECT_ROOT / "pyproject.toml").is_file()
    assert (config.FRONTEND_DIR / "index.html").is_file()
    assert config.SKILLS_DIR.is_dir()
    assert config.EVALS_DIR.is_dir()
    assert config.FLIGHT_DATA_PATH.is_file()
    assert config.FAISS_INDEX_PATH.is_file()


def test_project_relative_uses_posix_paths_inside_the_repo():
    inside = config.DOCUMENTS_DIR / "example.pdf"

    assert config.project_relative(inside) == (
        "data/raw/delta_small_pack/documents/example.pdf"
    )
    outside = config.PROJECT_ROOT.parent / "elsewhere.txt"

    assert config.project_relative(outside) == str(outside)


def test_settings_are_read_at_call_time(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "model-a")
    assert config.openai_model() == "model-a"

    monkeypatch.setenv("OPENAI_MODEL", "model-b")
    assert config.openai_model() == "model-b"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_setting_raises_a_clear_error(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
    else:
        monkeypatch.setenv("OPENAI_MODEL", value)

    with pytest.raises(config.ConfigError, match="OPENAI_MODEL"):
        config.openai_model()


def test_validate_settings_lists_every_missing_setting(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    with pytest.raises(config.ConfigError) as error:
        config.validate_settings()

    assert "OPENAI_API_KEY" in str(error.value)
    assert "OPENAI_MODEL" in str(error.value)


def test_validate_settings_passes_when_configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    monkeypatch.setenv("OPENAI_MODEL", "model")

    config.validate_settings()
