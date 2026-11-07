from __future__ import annotations

from pathlib import Path

import pytest

from agent_cyber.attachments import (
    AttachmentError,
    format_attachment_for_prompt,
    load_attachment,
)


def test_load_text_file(tmp_path: Path):
    path = tmp_path / "access.log"
    path.write_text("login failed\nuser=admin\n", encoding="utf-8")
    attachment = load_attachment(str(path))
    assert attachment.name == "access.log"
    assert "login failed" in attachment.content
    assert attachment.size > 0
    assert not attachment.truncated
    assert attachment.kind == "log"


def test_attachment_is_truncated(tmp_path: Path):
    path = tmp_path / "big.txt"
    path.write_text("A" * 500, encoding="utf-8")
    attachment = load_attachment(str(path), max_chars=50)
    assert attachment.truncated
    assert "[file truncated" in attachment.content
    assert len(attachment.content) < 200


def test_binary_is_rejected(tmp_path: Path):
    path = tmp_path / "binary.bin"
    path.write_bytes(b"\x00\x01\x02\x03" * 100)
    with pytest.raises(AttachmentError):
        load_attachment(str(path))


def test_missing_file_is_rejected(tmp_path: Path):
    with pytest.raises(AttachmentError):
        load_attachment(str(tmp_path / "missing.txt"))


def test_prompt_wrapper_escapes_attributes(tmp_path: Path):
    path = tmp_path / "a'b.txt"
    path.write_text("hello", encoding="utf-8")
    attachment = load_attachment(str(path))
    wrapped = format_attachment_for_prompt(attachment)
    assert "<attached_file" in wrapped
    assert "a&#x27;b.txt" in wrapped
    assert "hello" in wrapped
    assert wrapped.rstrip().endswith("</attached_file>")
