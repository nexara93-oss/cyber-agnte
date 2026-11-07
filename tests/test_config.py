from __future__ import annotations

from pathlib import Path

import pytest

from agent_cyber.config import (
    ConfigError,
    api_key_status,
    load_config,
    resolve_api_key,
    save_default_config,
    update_api_config,
)

ENV_KEYS = [
    "AGENT_CYBER_HOME",
    "AGENT_CYBER_DATA",
    "AGENT_CYBER_BASE_URL",
    "AGENT_CYBER_MODEL",
    "AGENT_CYBER_API_KEY",
    "AGENT_CYBER_API_KEY_ENV",
    "OPENAI_API_KEY",
]


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_CYBER_HOME", str(tmp_path / "home"))
    for key in ENV_KEYS:
        if key != "AGENT_CYBER_HOME":
            monkeypatch.delenv(key, raising=False)


def test_default_config_is_created():
    config = load_config()
    assert config.config_path is not None
    assert config.config_path.exists()
    assert config.api.base_url.startswith("https://")
    assert config.data_path == Path(config.config_path).parent / "data"
    assert config.data_path.exists()


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_CYBER_MODEL", "test-model")
    monkeypatch.setenv("AGENT_CYBER_BASE_URL", "http://127.0.0.1:9999/v1")
    config = load_config()
    assert config.api.model == "test-model"
    assert config.api.base_url == "http://127.0.0.1:9999/v1"


def test_invalid_url_is_rejected():
    path = save_default_config()
    path.write_text(
        '[api]\nbase_url = "not-a-url"\nmodel = "x"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_api_key_resolution(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    config = load_config()
    assert resolve_api_key(config) == "sk-test-123"
    assert "OPENAI_API_KEY" in api_key_status(config)


def test_force_overwrites_config():
    path = save_default_config()
    path.write_text("broken = true\n", encoding="utf-8")
    save_default_config(path, overwrite=True)
    assert "[api]" in path.read_text(encoding="utf-8")


def test_update_api_config_preserves_other_sections(tmp_path: Path):
    path = save_default_config(tmp_path / "config.toml")
    update_api_config(
        path,
        base_url="https://openrouter.ai/api/v1",
        model="openai/gpt-4o-mini",
        api_key_env="OPENROUTER_API_KEY",
    )
    config = load_config(path)
    assert config.api.base_url == "https://openrouter.ai/api/v1"
    assert config.api.model == "openai/gpt-4o-mini"
    assert config.api.api_key_env == "OPENROUTER_API_KEY"
    assert config.name == "Agent Cyber"
    assert path.with_name("config.toml.bak").exists()
    with pytest.raises(ConfigError):
        update_api_config(
            path,
            base_url="not-a-url",
            model="x",
            api_key_env="X",
        )


def test_provider_specific_keyring_key_is_resolved(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    config = load_config()
    config.api.api_key_env = "OPENROUTER_API_KEY"

    import agent_cyber.config as config_module

    def fake_keyring(username: str = "api_key") -> str | None:
        return "sk-or-test" if username == "openrouter_api_key" else None

    monkeypatch.setattr(config_module, "_keyring_get", fake_keyring)
    assert resolve_api_key(config) == "sk-or-test"
    assert "keychain" in api_key_status(config)
