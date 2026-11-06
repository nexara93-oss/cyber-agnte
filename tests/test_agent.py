from __future__ import annotations

from agent_cyber.agent import ChatAgent, _select_history
from agent_cyber.config import load_config
from agent_cyber.models import AttachmentRef, Message
from agent_cyber.skills import SkillLoader


def _config(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_CYBER_HOME", str(tmp_path / "home"))
    return load_config()


def test_system_prompt_contains_skill(tmp_path, monkeypatch):
    config = _config(tmp_path, monkeypatch)
    skills = SkillLoader().load_all()
    agent = ChatAgent(config, skills)
    prompt = agent.system_prompt("security-report")
    assert "Security Report Writer" in prompt
    assert "Cover" in prompt
    assert "security-report" in prompt


def test_build_messages_includes_attachment(tmp_path, monkeypatch):
    config = _config(tmp_path, monkeypatch)
    skills = SkillLoader().load_all()
    agent = ChatAgent(config, skills)
    history = [
        Message(
            id=1,
            session_id="s",
            role="user",
            content="Review this log",
            created_at="2026-01-01T00:00:00+00:00",
            attachments=[
                AttachmentRef(
                    id=1,
                    name="auth.log",
                    path="/tmp/auth.log",
                    size=10,
                    truncated=False,
                    kind="log",
                    content="failed login",
                )
            ],
        )
    ]
    messages = agent.build_messages(history, "log-analysis")
    assert messages[0]["role"] == "system"
    assert "Security Log Analysis" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "failed login" in messages[1]["content"]
    assert "<attached_file" in messages[1]["content"]


def test_extra_user_and_force_skill(tmp_path, monkeypatch):
    config = _config(tmp_path, monkeypatch)
    agent = ChatAgent(config, SkillLoader().load_all())
    messages = agent.build_messages(
        [],
        "log-analysis",
        force_skill="security-report",
        extra_user="write the report",
    )
    assert "Security Report Writer" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "write the report"}


def test_history_is_limited():
    history = [
        Message(
            id=index,
            session_id="s",
            role="user" if index % 2 == 0 else "assistant",
            content=f"message {index}",
            created_at="2026-01-01T00:00:00+00:00",
        )
        for index in range(100)
    ]
    selected = _select_history(history, max_chars=10_000, max_messages=6)
    assert len(selected) == 6
    assert selected[-1]["content"] == "message 99"
