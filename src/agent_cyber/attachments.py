"""Safe file loading for chat attachments.

Only text-like files and PDFs with extractable text are supported in this
build. Binary files are rejected rather than guessed at.
"""

from __future__ import annotations

import html
import os
from pathlib import Path

from .models import Attachment, human_size


class AttachmentError(RuntimeError):
    """Raised when a file cannot be attached safely."""


def load_attachment(
    path_value: str,
    *,
    max_chars: int = 60_000,
    max_bytes: int = 10_000_000,
) -> Attachment:
    raw_path = path_value.strip().strip('"').strip("'")
    if not raw_path:
        raise AttachmentError("Empty path")

    path = Path(os.path.expandvars(raw_path)).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()

    if not path.exists():
        raise AttachmentError(f"File not found: {path}")
    if not path.is_file():
        raise AttachmentError(f"Not a regular file: {path}")

    size = path.stat().st_size
    if size == 0:
        raise AttachmentError(f"File is empty: {path}")
    if size > max_bytes:
        raise AttachmentError(
            f"File is too large ({human_size(size)}). Limit: {human_size(max_bytes)}."
        )

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = _extract_pdf(path)
        kind = "pdf"
    else:
        text = _read_text(path)
        kind = suffix.lstrip(".") or "text"

    truncated = False
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n\n...[file truncated by Agent Cyber]"
        truncated = True

    return Attachment(
        name=path.name,
        path=str(path),
        size=size,
        content=text,
        truncated=truncated,
        kind=kind,
    )


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    sample = raw[:8192]
    if b"\x00" in sample:
        raise AttachmentError(
            f"Binary file rejected: {path.name}. Attach text, code, logs, or a PDF."
        )
    control = sum(1 for byte in sample if byte < 32 and byte not in (9, 10, 13))
    if sample and control / len(sample) > 0.10:
        raise AttachmentError(
            f"Binary file rejected: {path.name}. Attach text, code, logs, or a PDF."
        )

    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    for encoding in ("utf-8-sig", "cp1256", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AttachmentError(f"Could not decode {path.name} as text")


def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except Exception as exc:
        raise AttachmentError(
            "PDF support needs the 'pypdf' package. Run: pip install pypdf"
        ) from exc

    try:
        reader = PdfReader(str(path))
        chunks: list[str] = []
        for page in reader.pages:
            try:
                chunks.append(page.extract_text() or "")
            except Exception:
                chunks.append("")
    except Exception as exc:
        raise AttachmentError(f"Could not read PDF {path.name}: {exc}") from exc

    text = "\n\n".join(chunk.strip() for chunk in chunks if chunk.strip())
    if not text.strip():
        raise AttachmentError(
            f"No extractable text in {path.name}. Scanned/image-only PDFs are not supported."
        )
    return text


def format_attachment_for_prompt(attachment: Attachment) -> str:
    """Wrap attachment content in explicit, escaped delimiters.

    The system prompt tells the model that everything inside these tags is
    untrusted data, never instructions.
    """
    name = html.escape(attachment.name, quote=True)
    path = html.escape(attachment.path, quote=True)
    kind = html.escape(attachment.kind, quote=True)
    return (
        f'<attached_file name="{name}" path="{path}" kind="{kind}" '
        f'truncated="{str(attachment.truncated).lower()}">\n'
        f"{attachment.content}\n"
        f"</attached_file>"
    )


def attachment_label(attachment: Attachment | object) -> str:
    name = getattr(attachment, "name", "file")
    size = getattr(attachment, "size", 0)
    truncated = getattr(attachment, "truncated", False)
    suffix = " (truncated)" if truncated else ""
    return f"{name} · {human_size(int(size))}{suffix}"
