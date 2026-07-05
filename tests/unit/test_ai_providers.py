import pytest

from whosai.ai.providers import build_deepseek_chat_model


def test_deepseek_provider_defaults_to_v4_flash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    model = build_deepseek_chat_model()

    assert model.model_name == "deepseek-v4-flash"


def test_deepseek_provider_allows_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

    model = build_deepseek_chat_model()

    assert model.model_name == "deepseek-v4-pro"
