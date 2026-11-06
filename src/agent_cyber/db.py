"""SQLite persistence for sessions, messages, and attachments."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .models import Attachment, AttachmentRef, Message, Session


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    skill_id    TEXT,
    model       TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attachments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id  INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    path        TEXT NOT NULL,
    size        INTEGER NOT NULL,
    truncated   INTEGER NOT NULL DEFAULT 0,
    kind        TEXT NOT NULL DEFAULT 'text',
    content     TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
CREATE INDEX IF NOT EXISTS idx_attachments_message ON attachments(message_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class Database:
    """Small, synchronous SQLite wrapper.

    Textual runs the UI on one asyncio thread, so short synchronous writes are
    acceptable and keep the code easy to audit.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        try:
            self.conn.close()
        except sqlite3.Error:
            pass

    # ------------------------------------------------------------------ sessions
    def create_session(self, *, model: str | None = None, title: str = "New session") -> Session:
        session_id = _new_id()
        now = utc_now()
        with self.conn:
            self.conn.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at, skill_id, model) "
                "VALUES (?, ?, ?, ?, NULL, ?)",
                (session_id, title, now, now, model),
            )
        return Session(
            id=session_id,
            title=title,
            created_at=now,
            updated_at=now,
            skill_id=None,
            model=model,
        )

    def get_session(self, session_id: str) -> Session | None:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return self._row_to_session(row) if row else None

    def latest_session(self) -> Session | None:
        row = self.conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC, rowid DESC LIMIT 1"
        ).fetchone()
        return self._row_to_session(row) if row else None

    def list_sessions(self, limit: int = 30) -> list[Session]:
        rows = self.conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC, rowid DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def set_session_skill(self, session_id: str, skill_id: str | None) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE sessions SET skill_id = ?, updated_at = ? WHERE id = ?",
                (skill_id, utc_now(), session_id),
            )

    def set_session_model(self, session_id: str, model: str | None) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE sessions SET model = ?, updated_at = ? WHERE id = ?",
                (model, utc_now(), session_id),
            )

    def rename_session(self, session_id: str, title: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title[:120], utc_now(), session_id),
            )

    def delete_session(self, session_id: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def clear_session_messages(self, session_id: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            self.conn.execute(
                "UPDATE sessions SET title = 'New session', updated_at = ? WHERE id = ?",
                (utc_now(), session_id),
            )

    # ------------------------------------------------------------------ messages
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        attachments: Sequence[Attachment] | None = None,
    ) -> Message:
        now = utc_now()
        attachment_list = list(attachments or [])
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?)",
                (session_id, role, content, now),
            )
            message_id = int(cursor.lastrowid)
            for attachment in attachment_list:
                self.conn.execute(
                    "INSERT INTO attachments "
                    "(message_id, name, path, size, truncated, kind, content) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        message_id,
                        attachment.name,
                        attachment.path,
                        attachment.size,
                        int(attachment.truncated),
                        attachment.kind,
                        attachment.content,
                    ),
                )

            session = self.conn.execute(
                "SELECT title FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            title = session["title"] if session else "New session"
            new_title = title
            if role == "user" and title == "New session":
                basis = content.strip()
                if not basis and attachment_list:
                    basis = attachment_list[0].name
                if basis:
                    new_title = basis.replace("\n", " ")[:60]
            self.conn.execute(
                "UPDATE sessions SET updated_at = ?, title = ? WHERE id = ?",
                (now, new_title, session_id),
            )

        return Message(
            id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            created_at=now,
            attachments=[
                AttachmentRef(
                    id=None,
                    name=item.name,
                    path=item.path,
                    size=item.size,
                    truncated=item.truncated,
                    kind=item.kind,
                    content=item.content,
                )
                for item in attachment_list
            ],
        )

    def get_messages(self, session_id: str, limit: int | None = None) -> list[Message]:
        if limit is None:
            rows = self.conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM ("
                "  SELECT * FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?"
                ") ORDER BY id ASC",
                (session_id, limit),
            ).fetchall()

        if not rows:
            return []

        message_ids = [int(row["id"]) for row in rows]
        placeholders = ",".join("?" for _ in message_ids)
        attachment_rows = self.conn.execute(
            f"SELECT * FROM attachments WHERE message_id IN ({placeholders}) "
            "ORDER BY id ASC",
            message_ids,
        ).fetchall()
        attachments_by_message: dict[int, list[AttachmentRef]] = {}
        for row in attachment_rows:
            attachments_by_message.setdefault(int(row["message_id"]), []).append(
                AttachmentRef(
                    id=int(row["id"]),
                    name=row["name"],
                    path=row["path"],
                    size=int(row["size"]),
                    truncated=bool(row["truncated"]),
                    kind=row["kind"],
                    content=row["content"],
                )
            )

        return [
            Message(
                id=int(row["id"]),
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"],
                attachments=attachments_by_message.get(int(row["id"]), []),
            )
            for row in rows
        ]

    def count_messages(self, session_id: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()
        return int(row["n"]) if row else 0

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> Session:
        return Session(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            skill_id=row["skill_id"],
            model=row["model"],
        )
