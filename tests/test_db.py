from __future__ import annotations

from pathlib import Path

from agent_cyber.db import Database
from agent_cyber.models import Attachment


def _attachment(name: str = "sample.log") -> Attachment:
    return Attachment(
        name=name,
        path=f"/tmp/{name}",
        size=12,
        content="log content",
        truncated=False,
        kind="log",
    )


def test_session_and_messages(tmp_path: Path):
    db = Database(tmp_path / "test.db")
    session = db.create_session(model="test-model")
    assert session.title == "New session"

    user = db.add_message(session.id, "user", "Analyze this log", [_attachment()])
    assistant = db.add_message(session.id, "assistant", "It looks benign.")

    messages = db.get_messages(session.id)
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "Analyze this log"
    assert messages[0].attachments[0].name == "sample.log"
    assert messages[0].attachments[0].content == "log content"
    assert messages[1].id == assistant.id

    refreshed = db.get_session(session.id)
    assert refreshed is not None
    assert refreshed.title == "Analyze this log"
    assert db.count_messages(session.id) == 2
    db.close()


def test_list_and_clear(tmp_path: Path):
    db = Database(tmp_path / "test.db")
    first = db.create_session()
    second = db.create_session()
    db.add_message(first.id, "user", "first")
    db.add_message(second.id, "user", "second")

    sessions = db.list_sessions()
    assert {session.id for session in sessions} == {first.id, second.id}

    db.clear_session_messages(first.id)
    assert db.count_messages(first.id) == 0
    assert db.get_session(first.id).title == "New session"
    db.close()


def test_delete_session_cascades(tmp_path: Path):
    db = Database(tmp_path / "test.db")
    session = db.create_session()
    db.add_message(session.id, "user", "hello", [_attachment("x.txt")])
    db.delete_session(session.id)
    assert db.get_session(session.id) is None
    assert db.get_messages(session.id) == []
    db.close()


def test_latest_session(tmp_path: Path):
    db = Database(tmp_path / "test.db")
    first = db.create_session()
    second = db.create_session()
    db.add_message(first.id, "user", "first")
    db.add_message(second.id, "user", "second")
    latest = db.latest_session()
    assert latest is not None
    assert latest.id == second.id
    db.close()
