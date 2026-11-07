"""Chat orchestration: system prompt, skills, context assembly, streaming."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from importlib.resources import files

from .attachments import format_attachment_for_prompt
from .config import AppConfig
from .models import Message
from .provider import OpenAICompatibleProvider
from .skills import Skill, SkillLoader


class ChatAgent:
    def __init__(
        self,
        config: AppConfig,
        skills: dict[str, Skill],
        provider: OpenAICompatibleProvider | None = None,
    ):
        self.config = config
        self.skills = skills
        self.provider = provider or OpenAICompatibleProvider(config.api)
        self.base_prompt = _load_system_prompt()

    def system_prompt(
        self,
        active_skill_id: str | None = None,
        *,
        force_skill: str | None = None,
    ) -> str:
        skill_id = force_skill or active_skill_id
        skill = self.skills.get(skill_id) if skill_id else None

        parts = [self.base_prompt.strip()]
        parts.append(
            "## Installed skills\n"
            + SkillLoader.catalog_text(self.skills)
            + "\n\nUse `/skill <id>` to activate one. If no skill is active, "
            "answer directly and suggest a skill only when it clearly fits."
        )

        if skill:
            parts.append(
                f"## Active skill: {skill.name} (`{skill.id}`)\n"
                "Follow this methodology, structure, and quality rules closely.\n\n"
                f"{skill.body}"
            )
        else:
            parts.append(
                "No skill is currently active. Do not claim a skill was applied."
            )

        parts.append(f"Current date: {date.today().isoformat()}.")
        return "\n\n".join(parts)

    def build_messages(
        self,
        history: list[Message],
        active_skill_id: str | None = None,
        *,
        force_skill: str | None = None,
        extra_user: str | None = None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": self.system_prompt(
                    active_skill_id, force_skill=force_skill
                ),
            }
        ]

        selected = _select_history(
            history,
            max_chars=self.config.agent.max_context_chars,
            max_messages=self.config.agent.history_messages,
        )
        messages.extend(selected)
        if extra_user:
            messages.append({"role": "user", "content": extra_user})
        return messages

    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        greeting = _greeting_response(messages)
        if greeting is not None:
            yield greeting
            return
        async for chunk in self.provider.stream(messages, model=model):
            yield chunk


def _format_message(message: Message) -> str:
    text = message.content.strip()
    if message.role == "user" and message.attachments:
        blocks = [
            format_attachment_for_prompt(attachment)
            for attachment in message.attachments
            if attachment.content
        ]
        if blocks:
            text = (text + "\n\n" + "\n\n".join(blocks)).strip()
    return text


def _select_history(
    history: list[Message],
    *,
    max_chars: int,
    max_messages: int,
) -> list[dict[str, str]]:
    remaining = max_chars
    selected_rev: list[dict[str, str]] = []

    for message in reversed(history):
        if message.role not in {"user", "assistant"}:
            continue
        if len(selected_rev) >= max_messages:
            break

        text = _format_message(message)
        if not text:
            continue

        if len(text) > remaining:
            if not selected_rev:
                text = text[:remaining].rstrip() + "\n\n...[context truncated]"
                selected_rev.append({"role": message.role, "content": text})
            break

        selected_rev.append({"role": message.role, "content": text})
        remaining -= len(text)
        if remaining <= 0:
            break

    selected_rev.reverse()
    return selected_rev


def _greeting_response(messages: list[dict[str, str]]) -> str | None:
    """Handle common greetings deterministically so provider language defaults cannot override them."""
    latest = next((item["content"] for item in reversed(messages) if item.get("role") == "user"), "")
    greeting = " ".join(latest.strip().lower().split())
    greetings = {
        "hello": "Hello! How can I help you?",
        "hello!": "Hello! How can I help you?",
        "hi": "Hello! How can I help you?",
        "hi!": "Hello! How can I help you?",
        "hey": "Hello! How can I help you?",
        "hey!": "Hello! How can I help you?",
        "سلام عليكم": "وعليكم السلام! كيف يمكنني مساعدتك؟",
        "السلام عليكم": "وعليكم السلام! كيف يمكنني مساعدتك؟",
        "bonjour": "Bonjour ! Comment puis-je vous aider ?",
        "bonsoir": "Bonsoir ! Comment puis-je vous aider ?",
        "hola": "¡Hola! ¿Cómo puedo ayudarte?",
        "hola!": "¡Hola! ¿Cómo puedo ayudarte?",
    }
    return greetings.get(greeting)


def _load_system_prompt() -> str:
    return (
        files("agent_cyber")
        .joinpath("system_prompt.md")
        .read_text(encoding="utf-8")
    )
