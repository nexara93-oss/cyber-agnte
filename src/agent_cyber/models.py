"""Data models shared by the database, agent, and UI."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Attachment:
    """A file attached to a user message (content included for the model)."""

    name: str
    path: str
    size: int
    content: str
    truncated: bool = False
    kind: str = "text"

    @property
    def size_label(self) -> str:
        return human_size(self.size)


@dataclass(slots=True)
class AttachmentRef:
    """Persisted attachment metadata; content is kept in the database."""

    id: int | None
    name: str
    path: str
    size: int
    truncated: bool
    kind: str = "text"
    content: str = ""

    @property
    def size_label(self) -> str:
        return human_size(self.size)


@dataclass(slots=True)
class Message:
    id: int | None
    session_id: str
    role: str
    content: str
    created_at: str
    attachments: list[AttachmentRef] = field(default_factory=list)


@dataclass(slots=True)
class Session:
    id: str
    title: str
    created_at: str
    updated_at: str
    skill_id: str | None = None
    model: str | None = None


def human_size(size: int) -> str:
    """Return a compact human-readable size."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"
