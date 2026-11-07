# Agent Cyber

**Cyber AI · terminal-native security assistant**

Agent Cyber is a local terminal application that connects to any OpenAI-compatible
AI API. It gives you a chat workspace with file attachments, selectable security
skills, persistent sessions, and one-command report generation.

```text
┌ AGENT CYBER ──────────────────────────────────────────────┐
│  YOU                                                      │
│  Analyze this authentication log and tell me what matters.│
│                                                           │
│  AGENT CYBER                                              │
│  The log shows repeated failures against `admin` from...  │
│                                                           │
│  > /attach C:\logs\auth.log                               │
│  > /skill log-analysis                                    │
│  > /report Authentication Review                          │
└───────────────────────────────────────────────────────────┘
```

![Agent Cyber terminal UI](cyber-agnte\docsagent-cyber.svg)

> **Authorized use only.** Use Agent Cyber only on systems you own or have
> written permission to assess. The assistant refuses requests to attack third
> parties, deploy malware, cause denial of service, steal credentials, or evade
> defenses.

---

## Features

- **Terminal UI** built with Textual — works in Windows Terminal, PowerShell,
  Windows CMD (via Windows Terminal), Linux terminals, and over SSH.
- **Any OpenAI-compatible API** — OpenAI, OpenRouter, DeepSeek, Groq, Ollama,
  vLLM, LiteLLM, and similar providers.
- **Streaming responses** with Markdown rendering.
- **File attachments** — text, code, logs, configs, CSV/JSON/YAML, and PDFs.
- **Skills** — selectable security methodologies that shape the answer and the
  report.
- **Persistent sessions** in SQLite; resume old conversations.
- **Report generation** — `/report` writes a Markdown assessment report to disk.
- **Local-first** — no telemetry, no cloud storage, no data leaves your machine
  except the request you send to your chosen AI provider.

---

## Install

Requires Python 3.11+.

### Windows (PowerShell)

```powershell
python -m pip install -e .
```

If `agent-cyber` is not on `PATH`, use:

```powershell
python -m agent_cyber
```

### Linux / macOS

```bash
python3 -m pip install -e .
agent-cyber
```

For API keys in the OS keychain:

```bash
python -m pip install -e ".[secure]"
```

---

## Configure the AI API

Run once to create the configuration:

```powershell
python -m agent_cyber init
```

Or use the interactive setup (choose provider, model, and key):

```powershell
python -m agent_cyber setup
```

The setup writes the config and stores the key in the OS keychain when the
`secure` extra is installed; otherwise it sets the key for the current process
and prints the environment-variable command.

Edit the file printed by `python -m agent_cyber config`:

- Windows: `%APPDATA%\agent-cyber\config.toml`
- Linux: `~/.config/agent-cyber/config.toml`

Minimal config:

```toml
[api]
base_url = "https://api.openai.com/v1"
model = "gpt-4o-mini"
api_key_env = "OPENAI_API_KEY"
```

Then set the key.

### Windows

```powershell
setx OPENAI_API_KEY "sk-..."
# open a new terminal, then:
python -m agent_cyber test
python -m agent_cyber
```

### Linux

```bash
export OPENAI_API_KEY="sk-..."
python -m agent_cyber test
python -m agent_cyber
```

`agent-cyber test` sends a one-line request to verify the base URL, model, and
key before you open the full UI.

To persist, add the export to `~/.bashrc` or `~/.zshrc`.

### Provider examples

| Provider | `base_url` | Example model | Key env |
|---|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| OpenRouter | `https://openrouter.ai/api/v1` | `openai/gpt-4o-mini` | `OPENROUTER_API_KEY` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` | `DEEPSEEK_API_KEY` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| Ollama (local) | `http://localhost:11434/v1` | `llama3.2` | not required |

When using a non-OpenAI provider, also set:

```toml
api_key_env = "OPENROUTER_API_KEY"
```

or simply use one shared variable:

```powershell
setx AGENT_CYBER_API_KEY "sk-..."
```

`AGENT_CYBER_API_KEY` takes precedence and works with every provider.

Model names change; check your provider's documentation.

### Free OpenRouter models

OpenRouter offers a rotating set of `:free` models. Check the current list at
<https://openrouter.ai/models?max_price=0> or fetch it with:

```powershell
python -c "import json,urllib.request; d=json.load(urllib.request.urlopen('https://openrouter.ai/api/v1/models')); print('\n'.join(m['id'] for m in d['data'] if m['id'].endswith(':free')))"
```

Examples seen at the time of writing:

| Model | Context | Notes |
|---|---|---|
| `nvidia/nemotron-3.5-super-vl:free` | 1M | Text/image/video, reasoning, tools — current default |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | 1M | Text reasoning, tools |
| `google/gemma-4-31b-it:free` | 262k | Text/image/video, tools |
| `cohere/north-mini-code:free` | 256k | Code-oriented |
| `openrouter/free` | 200k | Router that picks an available free model |

Free-tier caveats:

- Rate limits and daily quotas are lower than paid models; some free endpoints
  may be temporarily unavailable.
- OpenRouter may require enabling a privacy setting that allows prompts to be
  logged or used for training on free endpoints. **Do not attach client data,
  logs with credentials, or personal data** until you have checked your
  OpenRouter privacy settings and data policy.
- Switch models inside the app with `/model <id>`; the choice is saved per
  session.

---

## Run

```powershell
python -m agent_cyber
```

or, if the script is on `PATH`:

```powershell
agent-cyber
```

From the repository, you can also use the launchers:

```powershell
.\run.bat          # Windows
```

```bash
./run.sh           # Linux / macOS
```

### Useful commands

| Command | Action |
|---|---|
| `/help` | Show all commands |
| `/attach <path>` | Attach a file to the next message |
| `/files` | List pending attachments |
| `/detach <n\|all>` | Remove attachments |
| `/skills` | List installed skills |
| `/skill <id>` | Activate a skill (`/skill off` to clear) |
| `/models [filter]` | Choose a configured provider, then live-search models; Delete removes the selected provider or hides a model |
| `/model [name]` | Show or set the model for this session |
| `/report [title]` | Generate a Markdown report from the session |
| `/new` | Start a new session |
| `/sessions` | List saved sessions |
| `/resume <id>` | Resume a session |
| `/config` | Show configuration and key status |
| `/key [provider [key]]` | Add or remove a provider API key |
| `/agents` | List Cyber agents or start setup in chat |
| `/agent <name>` | Switch to an agent, or answer its setup questions in chat |
| `/agent name \| mission \| scope \| rules` | Create or update an agent directly |
| `/clear` | Clear the current session |
| `/stop` | Stop generation |
| `/quit` | Exit |

While typing a `/` command, the suggestion box lists every command and filters
as you type; use `↑`/`↓` and `Tab` or `Enter` to choose one. Every picker card
has a **Cancel** button, and `Esc` also closes it without saving changes.

`/models` starts with the providers you can currently use. Select one with
`↑`/`↓` and `Enter`, or search by name, then choose a model. The **Delete**
button removes the highlighted provider: its API key is deleted from the OS
keychain/environment, its cached model list is cleared, and if it was the
active provider the configuration is reset. It disappears from `/models`
immediately.

On first launch, setup happens in the chat instead of a modal card: type `hi`
and answer the name, mission, authorized scope, and rules questions. You can
also create or update an agent directly with
`/agent name | mission | scope | rules`.

CLI commands: `agent-cyber init`, `agent-cyber setup`, `agent-cyber config`,
`agent-cyber test`, `agent-cyber skills`.

### Attaching files

Either type a path:

```text
/attach C:\logs\auth.log
```

or paste/type a path as the message. A path that points to a file is attached
instead of sent as text.

Supported: UTF-8/UTF-16/Windows-1256/Latin-1 text, logs, code, configs, CSV,
JSON, YAML, and PDFs with extractable text. Binary files and scanned PDFs are
rejected with a clear message.

Limits:

- 10 MB per file
- 60,000 characters per file sent to the model
- 8 pending attachments
- 120,000 characters of conversation context (older messages are trimmed)

Edit these in `config.toml` under `[agent]`.

### Keybindings

| Key | Action |
|---|---|
| `Enter` | Send |
| `Shift+Enter` / `Ctrl+J` | New line |
| `Esc` | Stop generation |
| `Ctrl+Q` | Quit |
| `Ctrl+N` | New session |
| `Ctrl+L` | Clear session |
| `Ctrl+O` | Focus `/attach` |

---

## Skills

Skills live in `src/agent_cyber/skills/builtin/`. Each is a `SKILL.md` with YAML
front matter and a Markdown methodology.

Built in:

| Skill | Purpose |
|---|---|
| `security-report` | Client-ready report structure, severity, evidence, closure wording |
| `vuln-triage` | Validate, deduplicate, score, and prioritize findings |
| `recon-plan` | Authorized, rate-limited reconnaissance plan with approvals |
| `log-analysis` | Timeline, hypotheses, indicators, containment, detection gaps |
| `hardening-review` | Windows/Linux CIS-style configuration review |
| `threat-model` | STRIDE, trust boundaries, mitigations |
| `incident-response` | NIST-style lifecycle with evidence preservation |
| `web-app-review` | OWASP WSTG/API review of traffic, code, or schemas |
| `windows-ad-review` | Read-only Active Directory and Windows configuration review |
| `linux-security-review` | Read-only Linux accounts, sudo, SSH, services, and container review |
| `detection-engineering` | Telemetry, detection logic, false positives, and test cases |

### Add your own skill

Create a directory under one of these locations:

- `./skills/<id>/SKILL.md` — project-specific
- `~/.config/agent-cyber/skills/<id>/SKILL.md` — user-wide
- `src/agent_cyber/skills/builtin/<id>/SKILL.md` — contribute a built-in

Example:

```markdown
---
id: api-review
name: API Security Review
description: Review an OpenAPI schema or API traffic for authorization and data-exposure issues.
version: 1.0.0
triggers:
  - api
  - openapi
---

# API Security Review

## Steps
1. Map endpoints, auth, roles, and data classes.
2. Check object-level authorization, function-level authorization, and rate limits.
3. Separate confirmed issues from hypotheses.
4. Produce a table: endpoint, issue, evidence, impact, remediation.
```

Use `/skill api-review` to activate it.

---

## Reports

`/report` asks the model to turn the current session into a structured Markdown
report, using the `security-report` skill. It is saved to:

- Windows: `%LOCALAPPDATA%\agent-cyber\reports\`
- Linux: `~/.local/share/agent-cyber/reports/`

The report is also stored in the session history. Missing evidence is marked
`Not provided`; the assistant is instructed not to invent findings or claim
absolute security.

---

## Data and privacy

| Data | Location |
|---|---|
| Config | `%APPDATA%\agent-cyber\config.toml` / `~/.config/agent-cyber/config.toml` |
| History DB | `%LOCALAPPDATA%\agent-cyber\history.db` / `~/.local/share/agent-cyber/history.db` |
| Reports | `.../agent-cyber/reports/` |
| API key | Environment variable, or OS keychain via `/key` |

- No telemetry.
- No cloud sync.
- Conversation and attachment content is sent to the AI provider you configure.
- Delete a session by removing the DB, or clear messages with `/clear`.
- Never store real credentials in attachments unless your provider and policy
  allow it.

`AGENT_CYBER_HOME` sets the config directory; data goes to
`$AGENT_CYBER_HOME/data`. `AGENT_CYBER_DATA` overrides the data directory
independently.

---

## Safety model

This build is a **chat and analysis assistant**, not an autonomous scanner:

- It cannot execute shell commands, scan networks, or read files you did not
  attach.
- It refuses malware, ransomware, DoS, credential theft, persistence, evasion,
  and attacks on third parties.
- It treats attachment content as untrusted data and resists prompt injection.
- It distinguishes `Verified`, `Likely`, and `Unverified` information.
- It never claims "100% secure" or "no vulnerabilities exist".

The full governed agent design (authorization gate, scope firewall, approvals,
sandbox, kill switch, four-gate closure) is documented in
`prompts/AGENT_SYSTEM_PROMPT.md` and `prompts/BUILD_PROMPT.md` for the next
milestone: safe tool execution.

---

## Architecture

```text
src/agent_cyber/
├─ app.py            Textual terminal UI and command handling
├─ cli.py            `agent-cyber` entry points
├─ agent.py          system prompt, context assembly, streaming
├─ provider.py       OpenAI-compatible HTTP/SSE client
├─ attachments.py    text/PDF loading, limits, prompt wrapping
├─ skills.py         skill discovery and front-matter parsing
├─ db.py             SQLite sessions, messages, attachments
├─ config.py         config, paths, API-key resolution
├─ models.py         shared dataclasses
├─ system_prompt.md  runtime safety and behavior prompt
└─ skills/builtin/   seven built-in methodologies
```

The AI is the reasoner; the application owns file limits, persistence, redaction
of key displays, and the rules injected into the system prompt.

---

## Development

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

44 tests cover config, attachments, skills, database, context assembly, chat onboarding, provider
parsing, and the Textual UI.

---

## Troubleshooting

**`agent-cyber` is not recognized**

Use `python -m agent_cyber`, or add Python's `Scripts` directory to `PATH`.

**401 / authentication failed**

Check the key environment variable and `api_key_env` in `config.toml`. On
Windows, `setx` only affects new terminals.

**404 / model not found**

Check `base_url` and `model`. For OpenAI-compatible gateways, the base URL
usually ends in `/v1`.

**No response / timeout**

Check network access, provider status, and `api.timeout`. Some providers require
a proxy.

**Arabic text looks left-aligned or unshaped**

Agent Cyber adds bidirectional shaping and right-aligns Arabic messages when the
optional Arabic reshaping packages are installed. Use a terminal and font with
Unicode and Arabic support, such as Windows Terminal with a suitable fallback
font. The assistant can also answer in English or French on request.

**A PDF is rejected**

Scanned/image-only PDFs have no extractable text. OCR it first, or attach the
text version.

---

## Rename

Change the display name in `config.toml`:

```toml
[app]
name = "Cyber AI Cyber"   # or "Agent Cyber"
tagline = "Cyber AI"
```

The package and command remain `agent-cyber`.

---

## License

MIT. See `LICENSE`.
