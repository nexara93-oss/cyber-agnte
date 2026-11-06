"""Configuration loading, paths, and API-key resolution."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import tomli_w

APP_SLUG = "agent-cyber"
DEFAULT_API_KEY_ENV = "OPENAI_API_KEY"
KEYRING_SERVICE = "agent-cyber"
KEYRING_USER = "api_key"


@dataclass(slots=True, frozen=True)
class ProviderInfo:
    id: str
    name: str
    base_url: str
    key_env: str
    requires_key: bool = True


PROVIDERS = (
    ProviderInfo("openai", "OpenAI", "https://api.openai.com/v1", "OPENAI_API_KEY"),
    ProviderInfo("anthropic", "Anthropic", "https://api.anthropic.com/v1", "ANTHROPIC_API_KEY"),
    ProviderInfo("google", "Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
    ProviderInfo("openrouter", "OpenRouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    ProviderInfo("deepseek", "DeepSeek", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
    ProviderInfo("groq", "Groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    ProviderInfo("mistral", "Mistral AI", "https://api.mistral.ai/v1", "MISTRAL_API_KEY"),
    ProviderInfo("xai", "xAI", "https://api.x.ai/v1", "XAI_API_KEY"),
    ProviderInfo("together", "Together AI", "https://api.together.xyz/v1", "TOGETHER_API_KEY"),
    ProviderInfo("fireworks", "Fireworks AI", "https://api.fireworks.ai/inference/v1", "FIREWORKS_API_KEY"),
    ProviderInfo("perplexity", "Perplexity", "https://api.perplexity.ai", "PERPLEXITY_API_KEY"),
    ProviderInfo("cohere", "Cohere", "https://api.cohere.com/v1", "COHERE_API_KEY"),
    ProviderInfo("huggingface", "Hugging Face", "https://router.huggingface.co/v1", "HF_TOKEN"),
    ProviderInfo("sambanova", "SambaNova", "https://api.sambanova.ai/v1", "SAMBANOVA_API_KEY"),
    ProviderInfo("novita", "Novita AI", "https://api.novita.ai/openai/v1", "NOVITA_API_KEY"),
    ProviderInfo("siliconflow", "SiliconFlow", "https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    ProviderInfo("ollama", "Ollama (Local)", "http://localhost:11434/v1", "OLLAMA_API_KEY", False),
)


def find_provider(provider_id: str) -> ProviderInfo | None:
    needle = provider_id.strip().lower()
    return next((provider for provider in PROVIDERS if provider.id == needle or provider.name.lower() == needle), None)


class ConfigError(RuntimeError):
    """Raised when the configuration cannot be loaded or is invalid."""


DEFAULT_CONFIG_TEXT = """\
# Agent Cyber configuration
# Location: see `agent-cyber config`

[app]
# Change to "Cyber AI Cyber" if you prefer the other name.
name = "Agent Cyber"
tagline = "Cyber AI"
language = "auto"

[api]
# Any OpenAI-compatible endpoint works.
# OpenAI:      https://api.openai.com/v1
# OpenRouter:  https://openrouter.ai/api/v1
# DeepSeek:    https://api.deepseek.com/v1
# Groq:        https://api.groq.com/openai/v1
# Ollama:      http://localhost:11434/v1
base_url = "https://api.openai.com/v1"
model = "gpt-4o-mini"
api_key_env = "OPENAI_API_KEY"
temperature = 0.2
max_tokens = 4096
timeout = 120.0
stream = true

# Optional extra headers, for example OpenRouter attribution:
# [api.extra_headers]
# "HTTP-Referer" = "http://localhost"
# "X-Title" = "Agent Cyber"

[agent]
max_context_chars = 120000
max_attachment_chars = 60000
max_file_bytes = 10000000
history_messages = 40

[ui]
show_sidebar = true
theme = "cyber"
"""


def config_dir() -> Path:
    """Return the configuration directory.

    ``AGENT_CYBER_HOME`` makes the app fully portable and is also used by tests.
    """
    override = os.getenv("AGENT_CYBER_HOME")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.getenv("APPDATA")
        return Path(base) / APP_SLUG if base else Path.home() / "AppData" / "Roaming" / APP_SLUG
    base = os.getenv("XDG_CONFIG_HOME")
    return Path(base) / APP_SLUG if base else Path.home() / ".config" / APP_SLUG


def data_dir() -> Path:
    """Return the data directory (history, reports, evidence)."""
    override = os.getenv("AGENT_CYBER_DATA")
    if override:
        return Path(override).expanduser()
    home = os.getenv("AGENT_CYBER_HOME")
    if home:
        return Path(home).expanduser() / "data"
    if os.name == "nt":
        base = os.getenv("LOCALAPPDATA")
        return Path(base) / APP_SLUG if base else Path.home() / "AppData" / "Local" / APP_SLUG
    base = os.getenv("XDG_DATA_HOME")
    return Path(base) / APP_SLUG if base else Path.home() / ".local" / "share" / APP_SLUG


def config_path() -> Path:
    return config_dir() / "config.toml"


def database_path() -> Path:
    return data_dir() / "history.db"


def reports_dir() -> Path:
    return data_dir() / "reports"


def user_skills_dir() -> Path:
    return config_dir() / "skills"


@dataclass(slots=True)
class ApiConfig:
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    api_key_env: str = DEFAULT_API_KEY_ENV
    temperature: float = 0.2
    max_tokens: int = 4096
    timeout: float = 120.0
    stream: bool = True
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AgentConfig:
    max_context_chars: int = 120_000
    max_attachment_chars: int = 60_000
    max_file_bytes: int = 10_000_000
    history_messages: int = 40


@dataclass(slots=True)
class UiConfig:
    show_sidebar: bool = True
    theme: str = "cyber"


@dataclass(slots=True)
class AppConfig:
    name: str = "Agent Cyber"
    tagline: str = "Cyber AI"
    language: str = "auto"
    api: ApiConfig = field(default_factory=ApiConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    config_path: Path | None = None
    data_path: Path | None = None


def _coerce(current: Any, value: Any) -> Any:
    if isinstance(current, bool):
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    if isinstance(current, int) and not isinstance(current, bool):
        return int(value)
    if isinstance(current, float):
        return float(value)
    if isinstance(current, dict):
        if not isinstance(value, dict):
            raise ConfigError(f"Expected a table, got {type(value).__name__}")
        return {str(k): str(v) for k, v in value.items()}
    if isinstance(current, str):
        return str(value)
    return value


def _apply_section(obj: Any, values: dict[str, Any]) -> None:
    for key, value in values.items():
        if not hasattr(obj, key):
            continue
        current = getattr(obj, key)
        setattr(obj, key, _coerce(current, value))


def _validate(config: AppConfig) -> None:
    parsed = urlparse(config.api.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError(
            f"api.base_url must be an http(s) URL, got {config.api.base_url!r}"
        )
    if not config.api.model.strip():
        raise ConfigError("api.model cannot be empty")
    if config.api.max_tokens <= 0:
        raise ConfigError("api.max_tokens must be greater than zero")
    if config.agent.max_context_chars < 2000:
        raise ConfigError("agent.max_context_chars must be at least 2000")
    if config.agent.max_attachment_chars < 500:
        raise ConfigError("agent.max_attachment_chars must be at least 500")


def save_default_config(path: Path | None = None, *, overwrite: bool = False) -> Path:
    target = Path(path) if path else config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        return target
    target.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
    if os.name != "nt":
        try:
            target.chmod(0o600)
        except OSError:
            pass
    return target


def update_api_config(
    path: Path,
    *,
    base_url: str,
    model: str,
    api_key_env: str,
) -> Path:
    """Update the [api] section while preserving the rest of the config.

    A ``.bak`` copy is written first. Comments are not preserved by the TOML
    round-trip; the backup keeps the original.
    """
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError(f"Invalid API base URL: {base_url!r}")
    if not model.strip():
        raise ConfigError("Model cannot be empty")
    if not api_key_env.strip():
        raise ConfigError("API key environment variable cannot be empty")

    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Could not read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("The configuration file must contain a TOML table")

    api = data.get("api")
    if not isinstance(api, dict):
        api = {}
        data["api"] = api
    api["base_url"] = base_url.strip()
    api["model"] = model.strip()
    api["api_key_env"] = api_key_env.strip()

    backup = path.with_name(path.name + ".bak")
    try:
        backup.write_bytes(path.read_bytes())
        path.write_text(tomli_w.dumps(data), encoding="utf-8")
        if os.name != "nt":
            path.chmod(0o600)
    except OSError as exc:
        raise ConfigError(f"Could not update {path}: {exc}") from exc
    return path


def load_config(path: Path | None = None) -> AppConfig:
    target = Path(path) if path else config_path()
    if not target.exists():
        save_default_config(target)

    try:
        with target.open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Could not read {target}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("The configuration file must contain a TOML table")

    config = AppConfig()
    app_values = raw.get("app", {})
    if isinstance(app_values, dict):
        _apply_section(config, app_values)
    api_values = raw.get("api", {})
    if isinstance(api_values, dict):
        _apply_section(config.api, api_values)
    agent_values = raw.get("agent", {})
    if isinstance(agent_values, dict):
        _apply_section(config.agent, agent_values)
    ui_values = raw.get("ui", {})
    if isinstance(ui_values, dict):
        _apply_section(config.ui, ui_values)

    # Environment overrides are convenient for CI, containers, and quick tests.
    if base_url := os.getenv("AGENT_CYBER_BASE_URL"):
        config.api.base_url = base_url
    if model := os.getenv("AGENT_CYBER_MODEL"):
        config.api.model = model
    if key_env := os.getenv("AGENT_CYBER_API_KEY_ENV"):
        config.api.api_key_env = key_env

    _validate(config)
    config.config_path = target
    config.data_path = data_dir()
    ensure_dirs(config)
    return config


def ensure_dirs(config: AppConfig | None = None) -> None:
    data = config.data_path if config and config.data_path else data_dir()
    data.mkdir(parents=True, exist_ok=True)
    (data / "reports").mkdir(parents=True, exist_ok=True)
    if config and config.config_path:
        config.config_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        config_dir().mkdir(parents=True, exist_ok=True)


def _keyring_get(username: str = KEYRING_USER) -> str | None:
    try:
        import keyring  # type: ignore[import-not-found]
    except Exception:
        return None
    try:
        value = keyring.get_password(KEYRING_SERVICE, username)
        return value.strip() if value else None
    except Exception:
        return None


def resolve_api_key(config: AppConfig | ApiConfig) -> str | None:
    """Resolve a key from env first, then the OS keychain.

    Accepts either the full application config or just the API section. The key
    is never read from, or written to, the TOML configuration.
    """
    api = config.api if isinstance(config, AppConfig) else config
    seen: set[str] = set()
    for env_name in ("AGENT_CYBER_API_KEY", api.api_key_env, DEFAULT_API_KEY_ENV):
        if not env_name or env_name in seen:
            continue
        seen.add(env_name)
        value = os.getenv(env_name)
        if value and value.strip():
            return value.strip()

    # Provider-specific entries written by `/key` use the key env name.
    for username in dict.fromkeys((api.api_key_env.lower(), KEYRING_USER)):
        if not username:
            continue
        value = _keyring_get(username)
        if value:
            return value
    return None


def store_api_key(key: str, key_env: str | None = None) -> bool:
    """Store a key in the OS keychain when available."""
    try:
        import keyring  # type: ignore[import-not-found]
    except Exception:
        return False
    try:
        username = key_env.lower() if key_env else KEYRING_USER
        keyring.set_password(KEYRING_SERVICE, username, key.strip())
        return True
    except Exception:
        return False


def resolve_provider_key(provider: ProviderInfo) -> str | None:
    value = os.getenv(provider.key_env, "").strip()
    if value:
        return value
    try:
        import keyring  # type: ignore[import-not-found]
        value = keyring.get_password(KEYRING_SERVICE, provider.key_env.lower())
        return value.strip() if value else None
    except Exception:
        return None


def delete_provider_key(provider: ProviderInfo) -> bool:
    os.environ.pop(provider.key_env, None)
    try:
        import keyring  # type: ignore[import-not-found]
        keyring.delete_password(KEYRING_SERVICE, provider.key_env.lower())
        return True
    except Exception:
        return False


def provider_key_status(provider: ProviderInfo) -> str:
    if not provider.requires_key:
        return "no key required"
    if os.getenv(provider.key_env, "").strip():
        return f"set ({provider.key_env})"
    return "set (OS keychain)" if resolve_provider_key(provider) else "missing"


def api_key_status(config: AppConfig) -> str:
    for env_name in ("AGENT_CYBER_API_KEY", config.api.api_key_env, DEFAULT_API_KEY_ENV):
        if env_name and os.getenv(env_name, "").strip():
            return f"set (environment: {env_name})"
    for username in dict.fromkeys((config.api.api_key_env.lower(), KEYRING_USER)):
        if username and _keyring_get(username):
            return "set (OS keychain)"
    return "missing"
