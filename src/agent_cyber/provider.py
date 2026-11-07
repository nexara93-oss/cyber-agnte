"""OpenAI-compatible chat provider with streaming support.

Works with OpenAI, OpenRouter, DeepSeek, Groq, Ollama's /v1 endpoint, vLLM,
LiteLLM, and other services that implement /chat/completions.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from .config import ApiConfig, resolve_api_key


class ProviderError(RuntimeError):
    """A user-facing provider error."""


@dataclass(slots=True)
class ModelInfo:
    """One model returned by the provider's ``/models`` endpoint."""

    id: str
    name: str = ""
    context_length: int | None = None
    prompt_price: float | None = None
    completion_price: float | None = None
    free: bool = False

    @property
    def context_label(self) -> str:
        if not self.context_length:
            return ""
        if self.context_length >= 1_000_000:
            value = f"{self.context_length / 1_000_000:.1f}".rstrip("0").rstrip(".")
            return f"{value}M ctx"
        if self.context_length >= 1_000:
            return f"{self.context_length // 1_000}k ctx"
        return f"{self.context_length} ctx"

    @property
    def price_label(self) -> str:
        if self.free:
            return "free"
        if self.prompt_price is None and self.completion_price is None:
            return ""
        prompt = _format_price(self.prompt_price)
        completion = _format_price(self.completion_price)
        return f"{prompt}/{completion} per 1M"


def _format_price(value: float | None) -> str:
    if value is None:
        return "?"
    per_million = value * 1_000_000
    if per_million == 0:
        return "$0"
    if per_million < 0.01:
        return f"${per_million:.4f}"
    return f"${per_million:.2f}"


def _as_price(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def models_url(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    if base.endswith("/models"):
        return base
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    if base.endswith("/v1") or base.endswith("/openai"):
        return base + "/models"
    return base + "/v1/models"


def parse_models(payload: Any) -> list[ModelInfo]:
    """Normalize a provider model list into :class:`ModelInfo` objects."""
    items: Any
    if isinstance(payload, dict):
        items = payload.get("data") or payload.get("models") or []
    else:
        items = payload
    if not isinstance(items, list):
        return []

    models: list[ModelInfo] = []
    for item in items:
        if isinstance(item, str):
            model_id = item.strip()
            if model_id:
                models.append(ModelInfo(id=model_id, name=model_id))
            continue
        if not isinstance(item, dict):
            continue

        model_id = str(item.get("id") or item.get("name") or "").strip()
        if not model_id:
            continue
        pricing = item.get("pricing")
        if not isinstance(pricing, dict):
            pricing = {}
        prompt_price = _as_price(pricing.get("prompt"))
        completion_price = _as_price(pricing.get("completion"))
        price_values = [
            _as_price(pricing.get(key))
            for key in ("prompt", "completion", "request", "image")
        ]
        known_prices = [value for value in price_values if value is not None]
        free = bool(known_prices) and all(value == 0 for value in known_prices)

        context_raw = (
            item.get("context_length")
            or item.get("context_window")
            or item.get("max_context_length")
        )
        try:
            context_length = int(context_raw) if context_raw else None
        except (TypeError, ValueError):
            context_length = None

        models.append(
            ModelInfo(
                id=model_id,
                name=str(item.get("name") or model_id),
                context_length=context_length,
                prompt_price=prompt_price,
                completion_price=completion_price,
                free=free,
            )
        )
    return models


def chat_completions_url(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1") or base.endswith("/openai"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content)


def parse_sse_event(data: str) -> tuple[bool, str]:
    """Parse one SSE ``data:`` payload.

    Returns ``(done, text)``. Raises ProviderError if the stream carries an
    error object.
    """
    data = data.strip()
    if not data:
        return False, ""
    if data == "[DONE]":
        return True, ""
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Malformed streaming response: {exc}") from exc

    if not isinstance(payload, dict):
        return False, ""
    if "error" in payload:
        error = payload["error"]
        if isinstance(error, dict):
            message = error.get("message") or error.get("detail") or str(error)
        else:
            message = str(error)
        raise ProviderError(f"Provider error: {message}")

    choices = payload.get("choices")
    if not choices or not isinstance(choices, list):
        return False, ""
    choice = choices[0] if isinstance(choices[0], dict) else {}
    delta = choice.get("delta")
    if isinstance(delta, dict):
        text = _content_to_text(delta.get("content"))
        if text:
            return False, text
    # Some providers return a non-streaming message shape inside the stream.
    message = choice.get("message")
    if isinstance(message, dict):
        return False, _content_to_text(message.get("content"))
    return False, ""


def _http_error_message(status: int, body: str, url: str) -> str:
    detail = body.strip().replace("\n", " ")[:500]
    if status == 401:
        hint = "Authentication failed. Check your API key and api_key_env setting."
    elif status == 403:
        hint = "Access denied. Check that the key is allowed to use this model."
    elif status == 404:
        hint = "Endpoint or model not found. Check base_url and model in the config."
    elif status == 429:
        hint = "Rate limited or out of quota. Wait and retry, or check your provider plan."
    elif 500 <= status < 600:
        hint = "The provider returned a server error. Retry in a moment."
    else:
        hint = f"HTTP {status} from the provider."
    suffix = f" Details: {detail}" if detail else ""
    return f"{hint}{suffix}"


class OpenAICompatibleProvider:
    def __init__(
        self,
        config: ApiConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.config = config
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
            "User-Agent": "AgentCyber/0.1",
        }
        api_key = resolve_api_key(self.config)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        headers.update(self.config.extra_headers)
        return headers

    def _payload(self, messages: list[dict[str, str]], model: str | None) -> dict[str, Any]:
        return {
            "model": (model or self.config.model),
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": self.config.stream,
        }

    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        url = chat_completions_url(self.config.base_url)
        payload = self._payload(messages, model)
        timeout = httpx.Timeout(self.config.timeout, connect=20.0)

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                if not self.config.stream:
                    response = await client.post(url, headers=self._headers(), json=payload)
                    if response.status_code >= 400:
                        raise ProviderError(
                            _http_error_message(response.status_code, response.text, url)
                        )
                    try:
                        data = response.json()
                    except json.JSONDecodeError as exc:
                        raise ProviderError("The provider returned invalid JSON.") from exc
                    choices = data.get("choices") or []
                    if not choices:
                        raise ProviderError("The provider returned no choices.")
                    message = choices[0].get("message") or {}
                    text = _content_to_text(message.get("content"))
                    if not text:
                        raise ProviderError("The provider returned an empty response.")
                    yield text
                    return

                async with client.stream("POST", url, headers=self._headers(), json=payload) as response:
                    if response.status_code >= 400:
                        body = (await response.aread()).decode("utf-8", "replace")
                        raise ProviderError(
                            _http_error_message(response.status_code, body, url)
                        )

                    content_type = response.headers.get("content-type", "").lower()
                    if "application/json" in content_type and "event-stream" not in content_type:
                        body = (await response.aread()).decode("utf-8", "replace")
                        try:
                            data = json.loads(body)
                        except json.JSONDecodeError as exc:
                            raise ProviderError(
                                "The provider returned invalid JSON."
                            ) from exc
                        choices = data.get("choices") or []
                        if not choices:
                            raise ProviderError("The provider returned no choices.")
                        message = choices[0].get("message") or {}
                        text = _content_to_text(message.get("content"))
                        if not text:
                            raise ProviderError("The provider returned an empty response.")
                        yield text
                        return

                    async for raw_line in response.aiter_lines():
                        line = raw_line.strip()
                        if not line or line.startswith(":"):
                            continue
                        if line.startswith("{"):
                            payload_text = line
                        elif line.startswith("data:"):
                            payload_text = line[5:].strip()
                        else:
                            continue
                        done, text = parse_sse_event(payload_text)
                        if done:
                            break
                        if text:
                            yield text
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "The provider timed out. Check your connection or raise api.timeout."
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(f"Could not reach the provider: {exc}") from exc

    async def list_models(self) -> list[ModelInfo]:
        """Fetch every model the provider advertises on its ``/models`` endpoint."""
        url = models_url(self.config.base_url)
        headers = self._headers()
        headers["Accept"] = "application/json"
        timeout = httpx.Timeout(min(self.config.timeout, 30.0), connect=15.0)

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = await client.get(url, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "The provider timed out while listing models."
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(f"Could not reach the provider: {exc}") from exc

        if response.status_code >= 400:
            raise ProviderError(
                _http_error_message(response.status_code, response.text, url)
            )
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ProviderError("The provider returned invalid JSON for /models.") from exc

        models = parse_models(payload)
        if not models:
            raise ProviderError("The provider returned no models for /models.")
        models.sort(key=lambda model: model.id.lower())
        return models
