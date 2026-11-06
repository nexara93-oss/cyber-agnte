"""Textual terminal UI for Agent Cyber."""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from rich.markup import escape
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message as TextualMessage
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, Markdown, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from .agent import ChatAgent
from .attachments import (
    AttachmentError,
    attachment_label,
    load_attachment,
)
from .config import (
    AppConfig,
    PROVIDERS,
    ProviderInfo,
    delete_provider_key,
    api_key_status,
    find_provider,
    resolve_provider_key,
    data_dir,
    database_path,
    load_config,
    resolve_api_key,
    store_api_key,
    update_api_config,
)
from .db import Database
from .models import Attachment, Message, Session
from .provider import ModelInfo, OpenAICompatibleProvider
from .skills import SkillLoader


try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:  # The app still works when bidi support is not installed.
    arabic_reshaper = None
    get_display = None


_ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]")


def contains_arabic(text: str) -> bool:
    return bool(_ARABIC_RE.search(text or ""))


def prepare_bidi_text(text: str) -> str:
    """Shape Arabic runs for terminals that need explicit bidi output."""
    if not text or arabic_reshaper is None or get_display is None:
        return text

    output: list[str] = []
    start: int | None = None
    for index, char in enumerate(text + "\n"):
        if _ARABIC_RE.match(char) or char in {" ", "\u0640", "\u200f", "\u200e"} and start is not None:
            if start is None:
                start = index
        else:
            if start is not None:
                output.append("\u202b" + get_display(arabic_reshaper.reshape(text[start:index])) + "\u202c")
                start = None
            if index < len(text):
                output.append(char)
    return "".join(output)


class ModelPickerScreen(ModalScreen[str]):
    """Scrollable, mouse- and keyboard-accessible provider model picker."""

    BINDINGS = [
        Binding("escape", "cancel_picker", "Cancel", priority=True),
        Binding("delete", "delete_model", "Hide model"),
    ]

    CSS = """
    ModelPickerScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.72);
    }
    ModelPickerScreen #model-card {
        width: 80;
        max-width: 94%;
        height: 15;
        max-height: 80%;
        border: tall #00e5a0;
        background: #0d1720;
        padding: 1 2;
    }
    ModelPickerScreen #model-title {
        height: 1;
        text-style: bold;
        color: #00e5a0;
    }
    ModelPickerScreen #model-search {
        height: 3;
        margin-top: 1;
        border: tall #334155;
        background: #0f1720;
    }
    ModelPickerScreen #model-search:focus {
        border: tall #00e5a0;
    }
    ModelPickerScreen #model-list {
        height: 1fr;
        margin-top: 1;
        border: solid #1d2a36;
        background: #0b0f14;
    }
    ModelPickerScreen #model-help {
        height: 1;
        margin-top: 1;
        color: #7f8c98;
    }
    """

    def __init__(self, models: list[ModelInfo], current: str):
        super().__init__()
        self.models = models
        self.current = current
        self._visible_models = list(models)

    def compose(self) -> ComposeResult:
        card = Vertical(id="model-card")
        card.styles.height = 14 + min(max(len(self.models), 1), 10)
        with card:
            yield Static(f"Select model · {len(self.models)} available", id="model-title")
            yield Input(
                placeholder="Search models by name…",
                id="model-search",
            )
            yield OptionList(*self._options(self.models), id="model-list")
            yield Static("Type to search  •  Tab/↑/↓ navigate  •  Enter/click select  •  Esc cancel", id="model-help")
            with Horizontal(classes="card-actions"):
                yield Button("Cancel", id="model-cancel", compact=True)

    def _options(self, models: list[ModelInfo]) -> list[Option]:
        options = []
        for model in models:
            details = "  ".join(
                part for part in (model.context_label, model.price_label) if part
            )
            marker = "  ← current" if model.id == self.current else ""
            label = escape(model.id)
            if details:
                label += f"  [dim]{escape(details)}[/dim]"
            label += marker
            options.append(Option(label, id=model.id))
        return options

    def on_mount(self) -> None:
        picker = self.query_one("#model-list", OptionList)
        for index, model in enumerate(self.models):
            if model.id == self.current:
                picker.highlighted = index
                break
        self.query_one("#model-search", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "model-search":
            return
        query = event.value.strip().lower()
        if query:
            visible = [
                model
                for model in self.models
                if query in model.id.lower() or query in model.name.lower()
            ]
        else:
            visible = list(self.models)
        self._visible_models = visible
        picker = self.query_one("#model-list", OptionList)
        picker.clear_options()
        if visible:
            picker.add_options(self._options(visible))
            picker.highlighted = 0

    def action_cancel_picker(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_delete_model(self) -> None:
        picker = self.query_one("#model-list", OptionList)
        if picker.highlighted is None:
            return
        option = picker.get_option_at_index(picker.highlighted)
        if option.id:
            self.dismiss(f"__delete_model__:{option.id}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "model-search" and self._visible_models:
            self.dismiss(self._visible_models[0].id)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)


class ProviderListScreen(ModalScreen[str]):
    """Searchable provider cards used by /key and /models."""

    BINDINGS = [
        Binding("escape", "cancel_picker", "Cancel", priority=True),
        Binding("delete", "delete_provider", "Delete provider"),
        Binding("up", "highlight_previous", "Previous provider", show=False, priority=True),
        Binding("down", "highlight_next", "Next provider", show=False, priority=True),
    ]

    CSS = """
    ProviderListScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.72);
    }
    ProviderListScreen #provider-card {
        width: 72;
        max-width: 94%;
        height: 15;
        max-height: 80%;
        border: tall #00e5a0;
        background: #0d1720;
        padding: 1 2;
    }
    ProviderListScreen #provider-search {
        height: 3;
        border: tall #334155;
        background: #0f1720;
    }
    ProviderListScreen #provider-search:focus { border: tall #00e5a0; }
    ProviderListScreen #provider-list {
        height: 1fr;
        margin-top: 1;
        border: solid #1d2a36;
        background: #0b0f14;
    }
    ProviderListScreen #provider-help {
        height: 1;
        margin-top: 1;
        color: #7f8c98;
    }
    """

    def __init__(self, providers: tuple[ProviderInfo, ...], title: str):
        super().__init__()
        self.providers = providers
        self._title = title
        self._visible = list(providers)

    def compose(self) -> ComposeResult:
        card = Vertical(id="provider-card")
        card.styles.height = 13 + min(max(len(self.providers), 1), 11)
        with card:
            yield Static(self._title, classes="provider-title")
            yield Input(placeholder="Search AI provider…", id="provider-search")
            yield OptionList(*self._options(self.providers), id="provider-list")
            yield Static(
                "↑/↓ select  •  Enter opens  •  Delete button removes provider + key",
                id="provider-help",
            )
            with Horizontal(classes="card-actions"):
                yield Button("Delete", id="provider-delete", compact=True, classes="danger")
                yield Button("Cancel", id="provider-cancel", compact=True)

    def _options(self, providers: list[ProviderInfo]) -> list[Option]:
        return [Option(f"{provider.name}  [dim]{provider.id}[/dim]", id=provider.id) for provider in providers]

    def on_mount(self) -> None:
        self.query_one("#provider-search", Input).focus()

    def action_cancel_picker(self) -> None:
        self.dismiss(None)

    def _move_highlight(self, offset: int) -> None:
        picker = self.query_one("#provider-list", OptionList)
        if not self._visible:
            return
        index = picker.highlighted if picker.highlighted is not None else 0
        index = max(0, min(index + offset, len(self._visible) - 1))
        picker.highlighted = index
        picker.scroll_to_highlight()

    def action_highlight_next(self) -> None:
        self._move_highlight(1)

    def action_highlight_previous(self) -> None:
        self._move_highlight(-1)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "provider-delete":
            self.action_delete_provider()
            return
        self.dismiss(None)

    def action_delete_provider(self) -> None:
        picker = self.query_one("#provider-list", OptionList)
        if picker.highlighted is None or not self._visible:
            return
        index = picker.highlighted
        if 0 <= index < len(self._visible):
            self.dismiss(f"__delete__:{self._visible[index].id}")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "provider-search":
            return
        query = event.value.strip().lower()
        visible = [p for p in self.providers if query in p.name.lower() or query in p.id.lower()] if query else list(self.providers)
        self._visible = visible
        picker = self.query_one("#provider-list", OptionList)
        picker.clear_options()
        if visible:
            picker.add_options(self._options(visible))
            picker.highlighted = 0

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._visible:
            self.dismiss(self._visible[0].id)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)


class ProviderKeyScreen(ModalScreen[str]):
    """Secure key entry for one provider."""

    BINDINGS = [Binding("escape", "cancel_key", "Cancel", priority=True)]

    CSS = """
    ProviderKeyScreen { align: center middle; background: rgba(0, 0, 0, 0.72); }
    ProviderKeyScreen #key-card { width: 62; height: 13; border: tall #00e5a0; background: #0d1720; padding: 1 2; }
    ProviderKeyScreen #provider-key { margin-top: 1; height: 3; border: tall #334155; background: #0f1720; }
    ProviderKeyScreen #provider-key:focus { border: tall #00e5a0; }
    ProviderKeyScreen #provider-key-help { height: 1; margin-top: 1; color: #7f8c98; }
    """

    def __init__(self, provider: ProviderInfo):
        super().__init__()
        self.provider = provider

    def compose(self) -> ComposeResult:
        with Vertical(id="key-card"):
            yield Static(f"Add API key · {self.provider.name}", classes="provider-title")
            yield Input(placeholder=f"{self.provider.key_env}", password=True, id="provider-key")
            yield Static("Enter saves  •  Esc cancels", id="provider-key-help")
            with Horizontal(classes="card-actions"):
                yield Button("Cancel", id="key-cancel", compact=True)

    def on_mount(self) -> None:
        self.query_one("#provider-key", Input).focus()

    def action_cancel_key(self) -> None:
        self.dismiss("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())


COMMANDS: tuple[tuple[str, str], ...] = (
    ("/help", "Show help"),
    ("/attach", "Attach a file"),
    ("/files", "List attachments"),
    ("/detach", "Detach an attachment"),
    ("/skills", "List skills"),
    ("/skill", "Activate a skill"),
    ("/models", "Choose provider and model"),
    ("/model", "Show or set current model"),
    ("/key", "Add or remove an API provider"),
    ("/sessions", "List sessions"),
    ("/resume", "Resume a session"),
    ("/report", "Generate a report"),
    ("/new", "Start a new session"),
    ("/clear", "Clear messages"),
    ("/config", "Show configuration"),
    ("/stop", "Stop generation"),
    ("/quit", "Exit Agent Cyber"),
)


HELP = """\
## Commands

| Command | What it does |
|---|---|
| `/help` | Show this help |
| `/attach <path>` | Attach a text, code, log, config, or PDF file |
| `/files` | List pending attachments |
| `/detach <n\\|all>` | Remove one or all pending attachments |
| `/skills` | List installed skills |
| `/skill <id>` | Activate a skill (`/skill off` to clear) |
| `/models [filter]` | Choose a provider, then search models; Delete hides a model or removes a provider |
| `/model [name]` | Show or set the model for this session |
| `/report [title]` | Generate a Markdown report from the session |
| `/new` | Start a new session |
| `/sessions` | List saved sessions |
| `/resume <id>` | Resume a saved session |
| `/config` | Show configuration and key status |
| `/key [provider [key]]` | Add or remove a provider API key |
| `/clear` | Clear the current session's messages |
| `/stop` | Stop the current generation |
| `/quit` | Exit |

**Tips:** type `/` to see every command; use `↑`/`↓` and `Tab` or `Enter` to
pick one. Paste or type a file path to attach it; use `Shift+Enter` for a new
line; `Esc` stops generation. Attachments are sent only with your next message.
"""


class ChatMessage(Vertical):
    """A rendered user, assistant, or system message."""

    def __init__(
        self,
        role: str,
        content: str,
        attachments: list[object] | None = None,
        *,
        streaming: bool = False,
    ):
        classes = f"msg {role}"
        if streaming:
            classes += " streaming"
        super().__init__(classes=classes)
        if contains_arabic(content):
            classes += " rtl"
            self.add_class("rtl")
        self.role = role
        self._content = content
        self._attachments = attachments or []
        self._body = Markdown(prepare_bidi_text(content) or "", classes="body")
        self._meta = Static(
            escape(self._meta_text(streaming)), classes="meta"
        )
        self._attachment_line = (
            Static(
                escape(
                    "attached: "
                    + ", ".join(attachment_label(item) for item in self._attachments)
                ),
                classes="attachments",
            )
            if self._attachments
            else None
        )

    def _meta_text(self, streaming: bool = False) -> str:
        if self.role == "user":
            return "YOU"
        if self.role == "assistant":
            return "AGENT CYBER · generating" if streaming else "AGENT CYBER"
        return "SYSTEM"

    def compose(self) -> ComposeResult:
        yield self._meta
        yield self._body
        if self._attachment_line is not None:
            yield self._attachment_line

    async def set_content(self, content: str, *, streaming: bool = False) -> None:
        self._content = content
        await self._body.update(prepare_bidi_text(content) or "")
        if contains_arabic(content):
            self.add_class("rtl")
        self._meta.update(escape(self._meta_text(streaming)))


class Composer(TextArea):
    """Multiline composer: Enter sends, Shift+Enter inserts a newline."""

    class Submitted(TextualMessage):
        def __init__(self, value: str):
            self.value = value
            super().__init__()

    async def _on_key(self, event: events.Key) -> None:
        box = self._command_box()
        if box is not None and event.key in {"down", "up"}:
            event.prevent_default()
            event.stop()
            index = box.highlighted if box.highlighted is not None else 0
            index += 1 if event.key == "down" else -1
            box.highlighted = max(0, min(index, box.option_count - 1))
            box.scroll_to_highlight()
            return
        if box is not None and event.key == "tab":
            option = box.get_option_at_index(box.highlighted or 0)
            if option.id:
                event.prevent_default()
                event.stop()
                self.load_text(f"{option.id} ")
                return
        if event.key in {"enter", "ctrl+enter"}:
            event.prevent_default()
            event.stop()
            value = self.text
            if box is not None:
                option = box.get_option_at_index(box.highlighted or 0)
                if option.id and option.id != value.strip():
                    value = option.id
            if value.strip():
                self.post_message(self.Submitted(value))
            return
        if event.key in {"shift+enter", "ctrl+j"}:
            event.prevent_default()
            event.stop()
            self.insert("\n")
            return
        await super()._on_key(event)

    def _command_box(self) -> OptionList | None:
        try:
            box = self.app.query_one("#command-suggestions", OptionList)
        except Exception:
            return None
        if box.styles.display == "none" or not box.option_count:
            return None
        return box


class AgentCyberApp(App[None]):
    TITLE = "Agent Cyber"
    SUB_TITLE = "Cyber AI // terminal"

    CSS = """
    Screen {
        background: #0b0f14;
        color: #d7e2ea;
    }
    Footer {
        background: #0d1720;
        color: #7f8c98;
    }
    #main {
        height: 1fr;
    }
    #sidebar {
        width: 34;
        min-width: 26;
        height: 1fr;
        padding: 1 2;
        background: #0c131a;
        border-right: solid #1d2a36;
        color: #b8c7d4;
    }
    #right {
        width: 1fr;
        height: 1fr;
    }
    #chat {
        height: 1fr;
        min-height: 0;
        padding: 1 2;
        background: #0b0f14;
        scrollbar-size-vertical: 1;
    }
    .card-actions {
        height: 1;
        margin-top: 1;
        align: right middle;
    }
    .card-actions Button {
        width: auto;
        min-width: 0;
        height: 1;
        margin-left: 1;
        padding: 0 1;
        border: none;
        background: transparent;
        color: #7f8c98;
        text-style: none;
    }
    .card-actions Button:hover {
        background: #13212e;
        color: #00e5a0;
    }
    .card-actions Button.danger {
        color: #ff8a80;
    }
    .card-actions Button.danger:hover {
        background: #2a1215;
        color: #ff5f56;
    }
    #command-suggestions {
        height: 0;
        display: none;
        margin: 0 2;
        border: none;
        background: #0d1720;
    }
    #composer {
        height: 5;
        margin: 0 2 1 2;
        padding: 0 1;
        border: tall #1d2a36;
        background: #0f1720;
        color: #e6eef5;
    }
    #composer:focus {
        border: tall #00e5a0;
    }
    ChatMessage {
        height: auto;
        margin: 0 0 1 0;
        padding: 0 1;
    }
    ChatMessage.user {
        border-left: thick #3b82f6;
        background: #0d1622;
    }
    ChatMessage.assistant {
        border-left: thick #00e5a0;
        background: #0c1518;
    }
    ChatMessage.system {
        border-left: thick #334155;
        background: #0b0f14;
        color: #9fb0c0;
    }
    ChatMessage .meta {
        height: auto;
        color: #7f8c98;
        text-style: bold;
    }
    ChatMessage.user .meta {
        color: #60a5fa;
    }
    ChatMessage.assistant .meta {
        color: #00e5a0;
    }
    ChatMessage .body {
        height: auto;
        background: transparent;
        margin: 0;
        padding: 0;
    }
    ChatMessage.rtl .body {
        text-align: right;
    }
    ChatMessage .attachments {
        height: auto;
        color: #ffb86b;
        padding: 0 0 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit_app", "Quit", priority=True),
        Binding("ctrl+n", "new_session", "New"),
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("ctrl+o", "focus_attach", "Attach"),
        Binding("escape", "stop_stream", "Stop", show=False, priority=True),
    ]

    def __init__(self, config: AppConfig | None = None):
        super().__init__()
        self.config = config or load_config()
        self.title = self.config.name
        self.sub_title = self.config.tagline
        self.db: Database | None = None
        self.skills: dict = {}
        self.agent: ChatAgent | None = None
        self.session: Session | None = None
        self.active_skill_id: str | None = None
        self.pending: list[Attachment] = []
        self.skill_errors: list[str] = []
        self._stream_task: asyncio.Task[None] | None = None
        self._streaming = False
        self._models_cache: list[ModelInfo] | None = None
        self._hidden_models: set[str] = set()
        self._disabled_providers: set[str] = set()

    # ------------------------------------------------------------------ compose
    def compose(self) -> ComposeResult:
        with Horizontal(id="main"):
            yield Static(id="sidebar")
            with Vertical(id="right"):
                yield VerticalScroll(id="chat")
                yield OptionList(id="command-suggestions")
                yield Composer(
                    id="composer",
                    placeholder="Ask Agent Cyber…  (/help for commands)",
                )
        yield Footer()

    async def on_mount(self) -> None:
        data = self.config.data_path or data_dir()
        data.mkdir(parents=True, exist_ok=True)
        self.reports_path.mkdir(parents=True, exist_ok=True)

        self.db = Database(database_path() if not self.config.data_path else data / "history.db")
        loader = SkillLoader()
        self.skills = loader.load_all()
        self.skill_errors = loader.errors
        self.agent = ChatAgent(self.config, self.skills)
        self.session = self.db.latest_session() or self.db.create_session(
            model=self.config.api.model
        )
        if self.session.skill_id and self.session.skill_id not in self.skills:
            self.session.skill_id = None
        self.active_skill_id = self.session.skill_id

        await self._render_history()
        if not self.db.get_messages(self.session.id):
            await self._system("Ready. Type `/help` for commands or describe a task to begin.")
        if not resolve_api_key(self.config) and not _is_local_url(self.config.api.base_url):
            await self._system(
                "**No API key detected.** Set `OPENAI_API_KEY` (or your provider's "
                "key environment variable), restart, or use `/key <key>` if the "
                "`keyring` extra is installed. See `/config`."
            )
        if self.skill_errors:
            await self._system(
                "**Skill loading warnings:** "
                + "; ".join(escape(item) for item in self.skill_errors)
            )

        self._update_sidebar()
        self.query_one(Composer).focus()

    # ------------------------------------------------------------------ state
    @property
    def model(self) -> str:
        if self.session and self.session.model:
            return self.session.model
        return self.config.api.model

    @property
    def reports_path(self) -> Path:
        return (self.config.data_path or data_dir()) / "reports"

    async def _render_history(self) -> None:
        chat = self.query_one("#chat", VerticalScroll)
        await chat.remove_children()
        if not self.session or not self.db:
            return
        for message in self.db.get_messages(self.session.id):
            await self._append(
                message.role,
                message.content,
                message.attachments,
            )

    async def _append(
        self,
        role: str,
        content: str,
        attachments: list[object] | None = None,
        *,
        streaming: bool = False,
    ) -> ChatMessage:
        chat = self.query_one("#chat", VerticalScroll)
        widget = ChatMessage(role, content, attachments, streaming=streaming)
        await chat.mount(widget)
        chat.scroll_end(animate=False)
        return widget

    async def _system(self, text: str) -> None:
        await self._append("system", text)

    def _update_sidebar(self) -> None:
        if not self.is_mounted:
            return
        try:
            sidebar = self.query_one("#sidebar", Static)
        except Exception:
            return

        model = self.model
        skill = self.active_skill_id or "none"
        status = "generating" if self._streaming else "ready"
        key = (
            "not required"
            if _is_local_url(self.config.api.base_url)
            else api_key_status(self.config)
        )
        session_id = self.session.id if self.session else "—"
        title = self.session.title if self.session else "—"

        lines = [
            f"[b]status[/]   {status}",
            f"[b]model[/]    {escape(model)}",
            f"[b]session[/]  {escape(session_id)}",
            f"[b]title[/]    {escape(title[:28])}",
            f"[b]skill[/]    {escape(skill)}",
            f"[b]api key[/]  {escape(key)}",
            "",
            "[b]pending files[/]",
        ]
        if self.pending:
            for index, attachment in enumerate(self.pending, start=1):
                lines.append(
                    f"  {index}. {escape(attachment.name)} "
                    f"[dim]({attachment.size_label})[/]"
                )
        else:
            lines.append("  [dim]none[/]")
        lines.extend(
            [
                "",
                "[b]commands[/]",
                "  /attach <path>",
                "  /skill <id>",
                "  /models",
                "  /report",
                "  /help",
                "",
                "[dim]Enter send · Shift+Enter newline[/]",
                "[dim]Esc stop generation[/]",
            ]
        )
        sidebar.update("\n".join(lines))

    # ------------------------------------------------------------------ input
    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if not isinstance(event.text_area, Composer) or event.text_area.id != "composer":
            return
        text = event.text_area.text
        suggestions = self.query_one("#command-suggestions", OptionList)
        suggestions.clear_options()
        if not text.startswith("/") or any(char.isspace() for char in text):
            suggestions.styles.height = 0
            suggestions.styles.display = "none"
            return
        prefix = text.lower()
        matches = [
            (name, description)
            for name, description in COMMANDS
            if name.startswith(prefix)
        ]
        if not matches:
            suggestions.styles.height = 0
            suggestions.styles.display = "none"
            return
        suggestions.add_options([Option(f"{escape(name)}  [dim]{escape(description)}[/dim]", id=name) for name, description in matches])
        suggestions.highlighted = 0
        suggestions.styles.display = "block"
        available = max(4, self.size.height - 7)
        suggestions.styles.height = min(len(matches), available)
        suggestions.scroll_home(animate=False)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "command-suggestions":
            composer = self.query_one("#composer", Composer)
            composer.load_text(f"{event.option.id} ")
            composer.focus()

    async def on_composer_submitted(self, event: Composer.Submitted) -> None:
        text = event.value.strip()
        composer = self.query_one(Composer)
        if not text and not self.pending:
            return
        composer.clear()

        if text.startswith("/"):
            await self._handle_command(text)
            return

        if self._streaming:
            await self._system("Still generating. Use `/stop` to cancel.")
            return

        if await self._maybe_attach_path(text):
            return

        await self._send(text)

    async def _maybe_attach_path(self, text: str) -> bool:
        if "\n" in text or len(text) > 500:
            return False
        candidate = text.strip().strip('"').strip("'")
        if not candidate:
            return False
        try:
            if Path(candidate).expanduser().is_file():
                await self._attach(candidate)
                return True
        except OSError:
            pass
        return False

    async def _send(self, text: str) -> None:
        if not self.db or not self.session:
            return
        content = text.strip() or "Please analyze the attached file(s)."
        attachments = self.pending[:]
        message = self.db.add_message(
            self.session.id, "user", content, attachments
        )
        await self._append("user", content, message.attachments)
        self.pending.clear()
        self._update_sidebar()

        history = self.db.get_messages(self.session.id)
        self._launch_stream(history)

    def _launch_stream(
        self,
        history: list[Message],
        *,
        force_skill: str | None = None,
        extra_user: str | None = None,
        report_path: Path | None = None,
    ) -> None:
        if self._streaming:
            return
        self._streaming = True
        self._update_sidebar()
        self._stream_task = asyncio.create_task(
            self._stream_into_chat(
                history,
                force_skill=force_skill,
                extra_user=extra_user,
                report_path=report_path,
            )
        )

    async def _stream_into_chat(
        self,
        history: list[Message],
        *,
        force_skill: str | None = None,
        extra_user: str | None = None,
        report_path: Path | None = None,
    ) -> None:
        if not self.agent or not self.db or not self.session:
            return
        widget = await self._append("assistant", "", streaming=True)
        buffer = ""
        last_update = 0.0
        saved_report: Path | None = None

        try:
            messages = self.agent.build_messages(
                history,
                self.active_skill_id,
                force_skill=force_skill,
                extra_user=extra_user,
            )
            async for chunk in self.agent.stream(messages, model=self.model):
                buffer += chunk
                now = time.monotonic()
                if now - last_update >= 0.08:
                    await widget.set_content(buffer, streaming=True)
                    self.query_one("#chat", VerticalScroll).scroll_end(animate=False)
                    last_update = now

            if not buffer.strip():
                buffer = "_(The provider returned an empty response.)_"
            await widget.set_content(buffer, streaming=False)
            self.db.add_message(self.session.id, "assistant", buffer)

            if report_path and not buffer.startswith("_(The provider"):
                try:
                    report_path.parent.mkdir(parents=True, exist_ok=True)
                    report_path.write_text(buffer, encoding="utf-8")
                    if os.name != "nt":
                        try:
                            report_path.chmod(0o600)
                        except OSError:
                            pass
                    saved_report = report_path
                except OSError as exc:
                    await self._system(
                        f"**Report could not be saved:** {escape(str(exc))}"
                    )

        except asyncio.CancelledError:
            suffix = "\n\n_[generation stopped by operator]_"
            if buffer.strip():
                await widget.set_content(buffer + suffix, streaming=False)
                self.db.add_message(self.session.id, "assistant", buffer + suffix)
            else:
                await widget.set_content("_[stopped]_", streaming=False)
            raise
        except Exception as exc:
            await widget.set_content(f"**Error:** {exc}", streaming=False)
            await self._system(f"Request failed: {escape(str(exc))}")
        finally:
            self._streaming = False
            self._stream_task = None
            self._update_sidebar()
            if saved_report is not None:
                await self._system(f"Report saved: `{saved_report}`")

    # ------------------------------------------------------------------ commands
    async def _handle_command(self, text: str) -> None:
        command, _, argument = text.partition(" ")
        command = command.lower()
        argument = argument.strip()

        if command == "/help":
            await self._system(HELP)
        elif command == "/attach":
            if not argument:
                await self._system("Usage: `/attach <path>`")
            else:
                await self._attach(argument)
        elif command == "/files":
            await self._list_pending()
        elif command == "/detach":
            await self._detach(argument)
        elif command == "/skills":
            await self._list_skills()
        elif command == "/skill":
            await self._set_skill(argument)
        elif command == "/new":
            await self._new_session()
        elif command == "/sessions":
            await self._list_sessions()
        elif command == "/resume":
            await self._resume(argument)
        elif command == "/report":
            await self._generate_report(argument)
        elif command == "/models":
            await self._list_models(argument)
        elif command == "/model":
            await self._set_model(argument)
        elif command == "/config":
            await self._show_config()
        elif command == "/key":
            await self._set_key(argument)
        elif command == "/clear":
            await self._clear()
        elif command == "/stop":
            self._stop_stream()
        elif command in {"/quit", "/exit"}:
            self.exit()
        elif command == "/version":
            from . import __version__

            await self._system(f"Agent Cyber `{__version__}`")
        else:
            await self._system(
                f"Unknown command `{escape(command)}`. Type `/help` for the list."
            )

    async def _attach(self, path: str) -> None:
        if len(self.pending) >= 8:
            await self._system("Maximum 8 pending attachments. Send or detach one first.")
            return
        try:
            attachment = load_attachment(
                path,
                max_chars=self.config.agent.max_attachment_chars,
                max_bytes=self.config.agent.max_file_bytes,
            )
        except AttachmentError as exc:
            await self._system(f"**Attachment failed:** {escape(str(exc))}")
            return

        if any(item.path == attachment.path for item in self.pending):
            await self._system(f"Already attached: `{escape(attachment.name)}`")
            return

        self.pending.append(attachment)
        note = " — truncated" if attachment.truncated else ""
        await self._system(
            f"Attached **{escape(attachment.name)}** "
            f"({attachment.size_label}){note}. It will be sent with your next message."
        )
        self._update_sidebar()

    async def _list_pending(self) -> None:
        if not self.pending:
            await self._system("No pending attachments.")
            return
        lines = ["## Pending attachments"]
        for index, attachment in enumerate(self.pending, start=1):
            suffix = " (truncated)" if attachment.truncated else ""
            lines.append(
                f"{index}. `{escape(attachment.name)}` — "
                f"{attachment.size_label}{suffix}"
            )
        await self._system("\n".join(lines))

    async def _detach(self, argument: str) -> None:
        if not self.pending:
            await self._system("No pending attachments.")
            return
        if argument.lower() == "all":
            self.pending.clear()
            await self._system("All pending attachments removed.")
        else:
            try:
                index = int(argument) - 1
                if index < 0 or index >= len(self.pending):
                    raise ValueError
            except ValueError:
                await self._system("Usage: `/detach <number>` or `/detach all`")
                return
            removed = self.pending.pop(index)
            await self._system(f"Removed `{escape(removed.name)}`.")
        self._update_sidebar()

    async def _list_skills(self) -> None:
        if not self.skills:
            await self._system("No skills installed.")
            return
        lines = ["## Skills"]
        for skill in self.skills.values():
            marker = " ← active" if skill.id == self.active_skill_id else ""
            lines.append(
                f"- `{skill.id}` — **{escape(skill.name)}** "
                f"({skill.source}){marker}\n  {escape(skill.description)}"
            )
        lines.append("\nActivate one with `/skill <id>`; clear with `/skill off`.")
        await self._system("\n".join(lines))

    async def _set_skill(self, argument: str) -> None:
        if not argument or argument.lower() == "list":
            await self._list_skills()
            return
        if argument.lower() == "off":
            self.active_skill_id = None
            if self.session and self.db:
                self.session.skill_id = None
                self.db.set_session_skill(self.session.id, None)
            await self._system("Skill deactivated.")
            self._update_sidebar()
            return
        skill = SkillLoader.find(self.skills, argument)
        if not skill:
            await self._system(
                f"Skill `{escape(argument)}` not found. Use `/skills` to list them."
            )
            return
        self.active_skill_id = skill.id
        if self.session and self.db:
            self.session.skill_id = skill.id
            self.db.set_session_skill(self.session.id, skill.id)
        await self._system(
            f"Active skill: **{escape(skill.name)}** (`{skill.id}`). "
            f"{escape(skill.description)}"
        )
        self._update_sidebar()

    async def _new_session(self) -> None:
        if not self.db:
            return
        if self._streaming:
            await self._system("Stop the current generation first with `/stop`.")
            return
        self.session = self.db.create_session(model=self.config.api.model)
        self.active_skill_id = None
        self.pending.clear()
        await self._render_history()
        self._update_sidebar()

    async def _list_sessions(self) -> None:
        if not self.db:
            return
        sessions = self.db.list_sessions()
        if not sessions:
            await self._system("No saved sessions.")
            return
        lines = ["## Sessions"]
        for session in sessions:
            marker = " ← current" if self.session and session.id == self.session.id else ""
            lines.append(
                f"- `{session.id}` — {escape(session.title[:60])}{marker}"
            )
        lines.append("\nResume with `/resume <id>`.")
        await self._system("\n".join(lines))

    async def _resume(self, argument: str) -> None:
        if not self.db:
            return
        if not argument:
            await self._system("Usage: `/resume <session-id>`")
            return
        if self._streaming:
            await self._system("Stop the current generation first with `/stop`.")
            return
        session = self.db.get_session(argument)
        if not session:
            await self._system(f"Session `{escape(argument)}` not found.")
            return
        self.session = session
        self.active_skill_id = (
            session.skill_id if session.skill_id in self.skills else None
        )
        self.pending.clear()
        await self._render_history()
        self._update_sidebar()

    async def _generate_report(self, title: str) -> None:
        if self._streaming:
            await self._system("Wait for the current generation, or use `/stop`.")
            return
        if not self.db or not self.session:
            return
        history = self.db.get_messages(self.session.id)
        if not history:
            await self._system("Nothing to report yet. Start a conversation first.")
            return

        title = title.strip() or "Security Assessment Report"
        safe_title = re.sub(r"[^A-Za-z0-9_-]+", "-", title).strip("-")[:50] or "report"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.reports_path / f"{stamp}-{safe_title}.md"

        instruction = (
            "Produce a complete, professional security assessment report in Markdown "
            "from the conversation above and its attachments. Return ONLY the report, "
            "starting with a title. Use the security-report structure: cover summary, "
            "scope, methodology, findings with severity and evidence, impact, "
            "remediation, coverage, limitations, and closure status. If an input or "
            "evidence is missing, write 'Not provided' instead of inventing it. Never "
            "claim absolute security. Mark unverified items clearly."
        )
        await self._system(
            "Generating a report from this session. It will be saved under "
            f"`{self.reports_path}`."
        )
        self._launch_stream(
            history,
            force_skill="security-report",
            extra_user=instruction,
            report_path=path,
        )

    async def _open_provider_models_by_id(self, provider_id: str | None, argument: str) -> None:
        if not provider_id:
            return
        if provider_id.startswith("__delete__:"):
            provider = find_provider(provider_id.split(":", 1)[1])
            if provider:
                await self._delete_provider(provider)
                await self._list_models(argument)
            return
        provider = find_provider(provider_id)
        if provider:
            await self._open_provider_models(provider, argument)

    def _configured_providers(self) -> list[ProviderInfo]:
        configured: list[ProviderInfo] = []
        for provider in PROVIDERS:
            if provider.id in self._disabled_providers:
                continue
            if resolve_provider_key(provider):
                configured.append(provider)
            elif not provider.requires_key and provider.base_url == self.config.api.base_url:
                configured.append(provider)
        return configured

    async def _delete_provider(self, provider: ProviderInfo) -> None:
        was_active = (
            self.config.api.base_url.rstrip("/") == provider.base_url.rstrip("/")
        )
        delete_provider_key(provider)
        self._disabled_providers.add(provider.id)
        self._models_cache = None

        if was_active:
            default = find_provider("openai") or PROVIDERS[0]
            self.config.api.base_url = default.base_url
            self.config.api.model = "gpt-4o-mini"
            self.config.api.api_key_env = default.key_env
            if self.session and self.db:
                self.session.model = None
                self.db.set_session_model(self.session.id, None)
            try:
                update_api_config(
                    self.config.config_path or (data_dir() / "config.toml"),
                    base_url=self.config.api.base_url,
                    model=self.config.api.model,
                    api_key_env=self.config.api.api_key_env,
                )
            except Exception:
                pass
            if self.agent:
                self.agent.provider = OpenAICompatibleProvider(self.config.api)

        await self._system(
            f"Provider **{escape(provider.name)}** removed: API key deleted "
            "and its cached models cleared."
        )
        if was_active:
            await self._system(
                "The active provider was reset. Use `/models` to choose another one."
            )
        self._update_sidebar()

    async def _list_models(self, argument: str) -> None:
        if not self.agent:
            return
        argument = argument.strip()
        if argument and find_provider(argument):
            provider = find_provider(argument)
            if provider:
                if provider.id in self._disabled_providers or (
                    provider.requires_key and not resolve_provider_key(provider)
                ):
                    await self._system(
                        f"Provider **{escape(provider.name)}** is not configured. "
                        "Use `/key` to add it."
                    )
                    return
                await self._open_provider_models(provider, "")
                return
        configured = self._configured_providers()
        if configured:
            self.push_screen(
                ProviderListScreen(
                    tuple(configured),
                    "Choose a provider · Delete button removes it",
                ),
                lambda provider_id: asyncio.create_task(
                    self._open_provider_models_by_id(provider_id, argument)
                ),
            )
            return
        if not resolve_api_key(self.config) and not _is_local_url(self.config.api.base_url):
            self._models_cache = None
            await self._system(
                "No AI providers configured. Use `/key` to add a provider."
            )
            return
        refresh = argument.lower() in {"refresh", "reload"}
        if refresh:
            argument = ""

        if self._models_cache is None or refresh:
            await self._system("Fetching the provider's model list…")
            try:
                self._models_cache = await self.agent.provider.list_models()
            except Exception as exc:
                await self._system(
                    f"**Could not list models:** {escape(str(exc))}"
                )
                return

        models = self._models_cache or []
        models = [model for model in models if model.id not in self._hidden_models]
        query = argument.lower()
        if query == "free":
            selected = [model for model in models if model.free]
            label = f"free models ({len(selected)} of {len(models)})"
        elif query:
            selected = [
                model
                for model in models
                if query in model.id.lower() or query in model.name.lower()
            ]
            label = (
                f"models matching `{escape(argument)}` "
                f"({len(selected)} of {len(models)})"
            )
        else:
            selected = list(models)
            label = f"all models ({len(selected)})"

        if not selected:
            await self._system(f"No models found for `{escape(argument)}`.")
            return

        self.push_screen(
            ModelPickerScreen(selected, self.model),
            self._on_model_selected,
        )

    async def _open_provider_models(self, provider: ProviderInfo, argument: str = "") -> None:
        api = replace(self.config.api, base_url=provider.base_url, api_key_env=provider.key_env)
        provider_client = OpenAICompatibleProvider(api)
        try:
            models = await provider_client.list_models()
        except Exception as exc:
            await self._system(f"**Could not list {escape(provider.name)} models:** {escape(str(exc))}")
            return
        models = [model for model in models if model.id not in self._hidden_models]
        query = argument.strip().lower()
        if query in {"refresh", "reload", "free"}:
            query = "" if query != "free" else query
        if query == "free":
            models = [model for model in models if model.free]
        elif query:
            models = [model for model in models if query in model.id.lower() or query in model.name.lower()]
        if not models:
            await self._system(f"No models found for {escape(provider.name)}.")
            return

        def selected(model_id: str | None) -> None:
            if not model_id:
                return
            if model_id.startswith("__delete_model__:"):
                model_id = model_id.split(":", 1)[1]
                self._hidden_models.add(model_id)
                self._models_cache = [item for item in (self._models_cache or []) if item.id != model_id]
                asyncio.create_task(self._system(f"Model `{escape(model_id)}` hidden from this list."))
                return
            asyncio.create_task(self._select_provider_model(provider, model_id))

        self.push_screen(ModelPickerScreen(models, self.model if provider.base_url == self.config.api.base_url else ""), selected)

    async def _select_provider_model(self, provider: ProviderInfo, model_id: str) -> None:
        await self._select_provider(provider)
        await self._set_model(model_id)

    def _on_model_selected(self, model_id: str | None) -> None:
        if not model_id:
            return
        if model_id.startswith("__delete_model__:"):
            removed = model_id.split(":", 1)[1]
            self._hidden_models.add(removed)
            self._models_cache = [item for item in (self._models_cache or []) if item.id != removed]
            asyncio.create_task(self._system(f"Model `{escape(removed)}` hidden from this list."))
            return
        asyncio.create_task(self._select_model(model_id))

    async def _select_model(self, model_id: str) -> None:
        await self._set_model(model_id)

    async def _set_model(self, argument: str) -> None:
        if not argument:
            await self._system(f"Current model: `{escape(self.model)}`")
            return
        if not self.session or not self.db:
            return
        self.session.model = argument
        self.db.set_session_model(self.session.id, argument)
        await self._system(f"Model for this session: `{escape(argument)}`")
        self._update_sidebar()

    async def _show_config(self) -> None:
        reports = self.reports_path
        lines = [
            "## Configuration",
            f"- **File:** `{self.config.config_path}`",
            f"- **Base URL:** `{self.config.api.base_url}`",
            f"- **Model:** `{escape(self.model)}`",
            f"- **Key:** {escape(api_key_status(self.config))}",
            f"- **Key env:** `{self.config.api.api_key_env}`",
            f"- **Data:** `{self.config.data_path or data_dir()}`",
            f"- **Reports:** `{reports}`",
            f"- **Skills:** {len(self.skills)} installed",
            "",
            "Edit the TOML file, set the environment variable, or use `/key` "
            "(requires the `keyring` extra).",
        ]
        await self._system("\n".join(lines))

    async def _set_key(self, argument: str) -> None:
        if argument:
            parts = argument.split(maxsplit=1)
            provider = find_provider(parts[0]) if parts else None
            if provider:
                if len(parts) == 2:
                    await self._save_provider_key(provider, parts[1])
                else:
                    await self._open_provider_key(provider.id)
                return
            await self._system("Unknown provider. Choose one from the list.")
        self.push_screen(
            ProviderListScreen(PROVIDERS, "Add an AI provider API key"),
            lambda provider_id: asyncio.create_task(self._open_provider_key(provider_id)),
        )

    async def _open_provider_key(self, provider_id: str | None) -> None:
        if not provider_id:
            return
        if provider_id.startswith("__delete__:"):
            provider = find_provider(provider_id.split(":", 1)[1])
            if provider:
                await self._delete_provider(provider)
            return
        provider = find_provider(provider_id)
        if provider:
            if not provider.requires_key:
                await self._select_provider(provider)
                return
            self.push_screen(
                ProviderKeyScreen(provider),
                lambda key: asyncio.create_task(self._save_provider_key(provider, key)),
            )

    async def _save_provider_key(self, provider: ProviderInfo, key: str) -> None:
        if not key:
            return
        self._disabled_providers.discard(provider.id)
        if store_api_key(key, provider.key_env):
            os.environ[provider.key_env] = key
            await self._system(f"API key for **{escape(provider.name)}** stored securely in the OS keychain.")
        else:
            os.environ[provider.key_env] = key
            await self._system(f"API key for **{escape(provider.name)}** set for this session; the OS keychain is unavailable.")
        await self._select_provider(provider)

    async def _select_provider(self, provider: ProviderInfo) -> None:
        self._disabled_providers.discard(provider.id)
        self.config.api.base_url = provider.base_url
        self.config.api.api_key_env = provider.key_env
        if provider.requires_key and not resolve_provider_key(provider):
            return
        self._models_cache = None
        try:
            update_api_config(
                self.config.config_path or (data_dir() / "config.toml"),
                base_url=provider.base_url,
                model=self.config.api.model,
                api_key_env=provider.key_env,
            )
        except Exception:
            pass
        if self.agent:
            self.agent.provider = OpenAICompatibleProvider(self.config.api)
        await self._system(f"Provider selected: **{escape(provider.name)}**. Use `/models` to choose a model.")
        self._update_sidebar()

    async def _clear(self) -> None:
        if not self.db or not self.session:
            return
        if self._streaming:
            await self._system("Stop the current generation first with `/stop`.")
            return
        self.db.clear_session_messages(self.session.id)
        self.pending.clear()
        await self._render_history()
        self._update_sidebar()

    # ------------------------------------------------------------------ actions
    def _stop_stream(self) -> None:
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            self.notify("Stopping generation…", severity="warning")
        else:
            self.notify("Nothing is generating.", severity="information")

    def action_stop_stream(self) -> None:
        self._stop_stream()

    def action_new_session(self) -> None:
        asyncio.create_task(self._new_session())

    def action_clear_chat(self) -> None:
        asyncio.create_task(self._clear())

    def action_focus_attach(self) -> None:
        composer = self.query_one(Composer)
        composer.focus()
        composer.clear()
        composer.insert("/attach ")

    def action_quit_app(self) -> None:
        self.exit()

    def on_unmount(self) -> None:
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
        if self.db:
            self.db.close()


def _is_local_url(url: str) -> bool:
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"} or host.startswith("192.168.")
