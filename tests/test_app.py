from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest
from textual.containers import VerticalScroll
from textual.widgets import OptionList

from agent_cyber.app import (
    COMMANDS,
    AgentCyberApp,
    ChatMessage,
    Composer,
    ModelPickerScreen,
    ProviderKeyScreen,
    ProviderListScreen,
)
from agent_cyber.config import PROVIDERS, find_provider
from agent_cyber.provider import ModelInfo

ENV_KEYS = [
    "AGENT_CYBER_DATA",
    "AGENT_CYBER_API_KEY",
    "AGENT_CYBER_API_KEY_ENV",
    "OPENAI_API_KEY",
]


@pytest.fixture(autouse=True)
def isolated_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_CYBER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENT_CYBER_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("AGENT_CYBER_MODEL", "mock-model")
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_app_mounts_with_skills():
    async def run():
        app = AgentCyberApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.session is not None
            assert len(app.skills) >= 7
            assert app.query_one("#composer", Composer)
            assert len(app.query_one("#chat", VerticalScroll).children) >= 1

    asyncio.run(run())


def test_skill_command():
    async def run():
        app = AgentCyberApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            composer = app.query_one(Composer)
            composer.focus()
            composer.insert("/skill security-report")
            await pilot.press("enter")
            await pilot.pause()
            assert app.active_skill_id == "security-report"
            assert app.session is not None
            assert app.session.skill_id == "security-report"

    asyncio.run(run())


def test_attach_and_send_with_fake_provider():
    async def run():
        home = Path(os.environ["AGENT_CYBER_HOME"])
        home.mkdir(parents=True, exist_ok=True)
        sample = home / "auth.log"
        sample.write_text(
            "2026-11-06T10:00:00Z login failed user=admin src=10.0.0.5\n",
            encoding="utf-8",
        )

        app = AgentCyberApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            composer = app.query_one(Composer)
            composer.focus()
            composer.insert(f"/attach {sample}")
            await pilot.press("enter")
            await pilot.pause()
            assert [item.name for item in app.pending] == ["auth.log"]

            async def fake_stream(messages, model=None):
                yield "The log shows a failed login."

            assert app.agent is not None
            app.agent.provider.stream = fake_stream

            composer.insert("Analyze this log")
            await pilot.press("enter")
            for _ in range(50):
                await asyncio.sleep(0.02)
                if not app._streaming:
                    break
            assert not app._streaming

            assert app.session is not None
            assert app.db is not None
            messages = app.db.get_messages(app.session.id)
            assert [message.role for message in messages] == ["user", "assistant"]
            assert messages[0].attachments[0].name == "auth.log"
            assert "failed login" in messages[1].content

    asyncio.run(run())


def test_report_command_saves_markdown():
    async def run():
        app = AgentCyberApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            composer = app.query_one(Composer)
            composer.focus()

            async def fake_stream(messages, model=None):
                yield "# Report\n\nNo verified findings."

            assert app.agent is not None
            app.agent.provider.stream = fake_stream

            composer.insert("hello")
            await pilot.press("enter")
            for _ in range(50):
                await asyncio.sleep(0.02)
                if not app._streaming:
                    break

            composer.insert("/report Test Report")
            await pilot.press("enter")
            for _ in range(50):
                await asyncio.sleep(0.02)
                if not app._streaming:
                    break

            reports = list(app.reports_path.glob("*.md"))
            assert reports
            assert "No verified findings" in reports[0].read_text(encoding="utf-8")

    asyncio.run(run())


def test_command_suggestions_show_every_command_and_filter_by_first_letter():
    expected = {
        "/": [name for name, _ in COMMANDS],
        "/k": ["/key"],
        "/m": ["/models", "/model"],
        "/s": ["/skills", "/skill", "/sessions", "/stop", "/settings"],
        "/r": ["/resume", "/report"],
        "/c": ["/clear", "/config"],
        "/q": ["/quit"],
    }

    async def run():
        app = AgentCyberApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            composer = app.query_one(Composer)
            composer.focus()
            box = app.query_one("#command-suggestions", OptionList)

            composer.load_text("/")
            await pilot.pause()
            assert [option.id for option in box.options] == expected["/"]
            assert box.size.height == len(COMMANDS)

            for query, names in expected.items():
                composer.load_text(query)
                await pilot.pause()
                assert [option.id for option in box.options] == names

    asyncio.run(run())


def test_every_modal_card_has_a_working_cancel_button():
    async def run():
        app = AgentCyberApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()

            app.push_screen(ProviderListScreen(PROVIDERS, "Choose a provider"))
            await pilot.pause()
            cancel = app.screen.query_one("#provider-cancel")
            assert cancel.region.height == 1
            assert app.screen.query_one("#provider-delete").region.height == 1
            await pilot.click("#provider-cancel")
            await pilot.pause()
            assert type(app.screen).__name__ == "Screen"

            provider = find_provider("openrouter")
            assert provider is not None
            app.push_screen(ProviderKeyScreen(provider))
            await pilot.pause()
            cancel = app.screen.query_one("#key-cancel")
            assert cancel.region.height == 1
            await pilot.click("#key-cancel")
            await pilot.pause()
            assert type(app.screen).__name__ == "Screen"

            models = [ModelInfo(id="free/model:free", name="Free", free=True)]
            app.push_screen(ModelPickerScreen(models, "free/model:free"))
            await pilot.pause()
            cancel = app.screen.query_one("#model-cancel")
            assert cancel.region.height == 1
            await pilot.click("#model-cancel")
            await pilot.pause()
            assert type(app.screen).__name__ == "Screen"

    asyncio.run(run())


def test_onboarding_asks_questions_in_chat_and_saves_agent():
    answers = [
        "Hydra",
        "authorized penetration testing for my lab",
        "lab network 10.0.0.0/24",
        "ask before destructive actions",
    ]

    async def run():
        app = AgentCyberApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            chat = app.query_one("#chat", VerticalScroll)
            assert type(app.screen).__name__ == "Screen"

            await app._begin_agent_onboarding()
            await pilot.pause()
            assert app._onboarding_step == "awaiting_start"
            assert type(app.screen).__name__ == "Screen"

            composer = app.query_one(Composer)
            composer.focus()
            composer.load_text("hi")
            await pilot.press("enter")
            await pilot.pause()
            assert app._onboarding_step == "name"
            assert "Name" in chat.children[-1]._content

            for answer in answers:
                composer.load_text(answer)
                await pilot.press("enter")
                await pilot.pause()

            assert app._onboarding_step is None
            assert app.active_agent == "Hydra"
            profile = app.cyber_agents["hydra"]
            assert profile["mission"] == answers[1]
            assert profile["scope"] == answers[2]
            assert profile["rules"] == answers[3]
            saved = json.loads(app.agents_file.read_text(encoding="utf-8"))
            assert saved["hydra"]["mission"] == answers[1]

            messages = [
                child for child in chat.children if isinstance(child, ChatMessage)
            ]
            user = next(message for message in messages if message.role == "user")
            assistant = next(
                message for message in messages if message.role == "assistant"
            )
            user_bubble = user.query_one(".bubble").region
            assistant_bubble = assistant.query_one(".bubble").region
            assert user_bubble.x > assistant_bubble.x
            assert user_bubble.x + user_bubble.width <= chat.region.x + chat.region.width

    asyncio.run(run())


def test_agent_command_creates_agent_without_a_modal():
    async def run():
        app = AgentCyberApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            composer = app.query_one(Composer)
            composer.focus()
            composer.load_text("/agent Hydra | lab pentest | 10.0.0.0/24 | ask first")
            await pilot.press("enter")
            await pilot.pause()

            assert type(app.screen).__name__ == "Screen"
            assert app.active_agent == "Hydra"
            profile = app.cyber_agents["hydra"]
            assert profile["mission"] == "lab pentest"
            assert profile["scope"] == "10.0.0.0/24"
            assert profile["rules"] == "ask first"

    asyncio.run(run())


def test_chat_messages_render_as_opposite_aligned_bubbles():
    async def run():
        app = AgentCyberApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            chat = app.query_one("#chat", VerticalScroll)
            user = await app._append("user", "hi")
            assistant = await app._append("assistant", "Hello, how can I help?")
            await pilot.pause()

            user_bubble = user.query_one(".bubble")
            assistant_bubble = assistant.query_one(".bubble")
            assert user_bubble.border_title == "YOU"
            assert assistant_bubble.border_title == "AGENT CYBER"
            assert user_bubble.region.x > assistant_bubble.region.x
            assert user_bubble.region.width < assistant_bubble.region.width
            assert assistant_bubble.region.x >= chat.region.x
            assert (
                user_bubble.region.x + user_bubble.region.width
                <= chat.region.x + chat.region.width
            )

    asyncio.run(run())


def test_models_lists_providers_and_delete_removes_key_and_models(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("AGENT_CYBER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("AGENT_CYBER_MODEL", "nvidia/nemotron-3.5-super-vl:free")
    monkeypatch.setenv("AGENT_CYBER_API_KEY_ENV", "OPENROUTER_API_KEY")

    import agent_cyber.app as app_module

    deleted: list[str] = []

    def fake_delete(provider):
        os.environ.pop(provider.key_env, None)
        deleted.append(provider.id)
        return True

    monkeypatch.setattr(app_module, "delete_provider_key", fake_delete)

    async def run():
        app = AgentCyberApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app._models_cache = [
                ModelInfo(id="old/model:free", name="Old", free=True)
            ]

            composer = app.query_one(Composer)
            composer.focus()
            composer.load_text("/models")
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, ProviderListScreen)
            assert [provider.id for provider in app.screen._visible] == ["openrouter"]

            await pilot.click("#provider-delete")
            await pilot.pause()
            await asyncio.sleep(0.1)

            assert deleted == ["openrouter"]
            assert os.getenv("OPENROUTER_API_KEY") is None
            assert app._models_cache is None
            assert app.config.api.base_url == "https://api.openai.com/v1"
            assert app.session is not None
            assert app.session.model is None
            assert not isinstance(app.screen, ProviderListScreen)
            assert "No AI providers configured" in app.query_one("#chat").children[-1]._content

    asyncio.run(run())
