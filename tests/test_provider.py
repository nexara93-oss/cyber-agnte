from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from agent_cyber.config import ApiConfig
from agent_cyber.provider import (
    OpenAICompatibleProvider,
    ProviderError,
    chat_completions_url,
    models_url,
    parse_sse_event,
)


def test_chat_completions_url():
    assert (
        chat_completions_url("https://api.openai.com/v1")
        == "https://api.openai.com/v1/chat/completions"
    )
    assert (
        chat_completions_url("https://api.openai.com/v1/")
        == "https://api.openai.com/v1/chat/completions"
    )
    assert (
        chat_completions_url("http://localhost:11434/v1")
        == "http://localhost:11434/v1/chat/completions"
    )
    assert (
        chat_completions_url("https://example.com/chat/completions")
        == "https://example.com/chat/completions"
    )
    assert (
        chat_completions_url("https://example.com")
        == "https://example.com/v1/chat/completions"
    )
    assert (
        chat_completions_url("https://generativelanguage.googleapis.com/v1beta/openai")
        == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    )


def test_models_url():
    assert (
        models_url("https://openrouter.ai/api/v1")
        == "https://openrouter.ai/api/v1/models"
    )
    assert (
        models_url("https://api.openai.com/v1/")
        == "https://api.openai.com/v1/models"
    )
    assert (
        models_url("https://generativelanguage.googleapis.com/v1beta/openai")
        == "https://generativelanguage.googleapis.com/v1beta/openai/models"
    )


def test_parse_sse_event():
    payload = json.dumps({"choices": [{"delta": {"content": "hello"}}]})
    assert parse_sse_event(payload) == (False, "hello")
    assert parse_sse_event("[DONE]") == (True, "")
    assert parse_sse_event("") == (False, "")


def test_parse_sse_event_list_content():
    payload = json.dumps(
        {"choices": [{"delta": {"content": [{"type": "text", "text": "hi"}]}}]}
    )
    assert parse_sse_event(payload) == (False, "hi")


def test_parse_sse_error():
    payload = json.dumps({"error": {"message": "bad key"}})
    with pytest.raises(ProviderError, match="bad key"):
        parse_sse_event(payload)


def test_provider_streams_with_mock_transport(monkeypatch):
    monkeypatch.setenv("AGENT_CYBER_API_KEY", "sk-test")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer sk-test"
        body = json.loads(request.content)
        assert body["model"] == "mock-model"
        assert body["stream"] is True
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                'data: {"choices":[{"delta":{"content":"Hello "}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"world"}}]}\n\n'
                "data: [DONE]\n\n"
            ).encode(),
        )

    config = ApiConfig(
        base_url="https://example.com/v1",
        model="mock-model",
        stream=True,
    )
    provider = OpenAICompatibleProvider(config, transport=httpx.MockTransport(handler))

    async def collect():
        return [chunk async for chunk in provider.stream([{"role": "user", "content": "hi"}])]

    assert asyncio.run(collect()) == ["Hello ", "world"]


def test_provider_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    config = ApiConfig(base_url="https://example.com/v1", model="mock", stream=True)
    provider = OpenAICompatibleProvider(config, transport=httpx.MockTransport(handler))

    async def run():
        async for _ in provider.stream([{"role": "user", "content": "hi"}]):
            pass

    with pytest.raises(ProviderError, match="Authentication failed"):
        asyncio.run(run())


def test_provider_non_stream_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "plain answer"}}]},
        )

    config = ApiConfig(base_url="https://example.com/v1", model="mock", stream=False)
    provider = OpenAICompatibleProvider(config, transport=httpx.MockTransport(handler))

    async def collect():
        return [chunk async for chunk in provider.stream([{"role": "user", "content": "hi"}])]

    assert asyncio.run(collect()) == ["plain answer"]


def test_provider_lists_models():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/models"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "free/model:free",
                        "name": "Free Model",
                        "context_length": 1_000_000,
                        "pricing": {"prompt": "0", "completion": "0"},
                    },
                    {
                        "id": "paid/model",
                        "name": "Paid Model",
                        "context_length": 128_000,
                        "pricing": {"prompt": "0.0000005", "completion": "0.0000015"},
                    },
                ]
            },
        )

    config = ApiConfig(base_url="https://openrouter.ai/api/v1", model="mock")
    provider = OpenAICompatibleProvider(config, transport=httpx.MockTransport(handler))

    models = asyncio.run(provider.list_models())
    assert [model.id for model in models] == ["free/model:free", "paid/model"]
    assert models[0].free is True
    assert models[0].context_label == "1M ctx"
    assert models[1].free is False
    assert models[1].price_label == "$0.50/$1.50 per 1M"
