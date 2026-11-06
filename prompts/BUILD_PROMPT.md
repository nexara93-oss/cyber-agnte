# Build Prompt — JANUS Security Assessment Platform

> **How to use this file:** give this document to a coding agent (Claude Code, Codex, Cursor, etc.) together with `AGENT_SYSTEM_PROMPT.md`. The agent prompt defines runtime behavior; this document defines the product to build. The coding agent must not weaken or bypass the safety requirements below.

---

## 1. Mission

Build **JANUS**, a production-grade, terminal-first platform for **authorized** security assessments on **Windows and Linux**.

The platform runs an AI agent that performs reconnaissance, enumeration, vulnerability analysis, controlled validation, defensive review, and professional reporting — strictly inside a signed Rules of Engagement (RoE).

**Core principle:** the LLM is the reasoner, never the security boundary. Authorization, scope, rate limits, prohibited actions, approvals, sandboxing, and the kill switch are enforced by deterministic code around the model.

**Legal boundary:** JANUS may only be used against systems the operator owns or has explicit written permission to test. The product must make unauthorized use difficult and auditable.

---

## 2. Deliverables

A monorepo with:

```text
janus/
├─ pyproject.toml
├─ README.md
├─ docker-compose.yml
├─ config/
│  ├─ roe.example.yaml
│  └─ janus.example.toml
├─ backend/
│  └─ janus/
│     ├─ api/            # FastAPI routes + WebSocket streams
│     ├─ cli/            # Typer CLI
│     ├─ tui/            # Textual terminal UI
│     ├─ agent/          # orchestrator, planner, executor, critic
│     ├─ policy/         # RoE validation, scope guard, risk classifier
│     ├─ tools/          # tool gateway + registry + sandbox adapters
│     ├─ skills/         # skill engine + manifests
│     ├─ memory/         # episodic/semantic memory, vector index
│     ├─ evidence/       # hashing, encryption, redaction
│     ├─ reporting/      # Jinja2 templates, PDF/JSON export
│     ├─ models/         # SQLAlchemy models + Pydantic schemas
│     └─ audit/          # append-only audit log
├─ skills/               # YAML manifests + handler modules
├─ frontend/             # React + TypeScript + Vite
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  └─ e2e/
└─ docs/
   ├─ architecture.md
   ├─ threat-model.md
   ├─ safety.md
   └─ operations.md
```

Provide Docker images and a one-command local demo against an intentionally vulnerable lab (Juice Shop / DVWA) that produces a sample report.

---

## 3. Technology stack

### Backend

- Python 3.12+, managed with `uv`
- FastAPI + Uvicorn
- Pydantic v2
- SQLAlchemy 2 + Alembic
- Typer (CLI) + Textual (TUI) + Rich
- httpx, websockets
- Jinja2 (reports), WeasyPrint (PDF)
- structlog (structured logging)
- keyring + cryptography (secrets, encryption at rest)
- pytest, pytest-asyncio, respx, Playwright (E2E)

### Storage

- SQLite for local-first deployments; PostgreSQL optional for teams
- `sqlite-vec` or Chroma for semantic memory
- Local encrypted evidence store (age or libsodium)
- Append-only JSONL audit log with hash chaining

### Frontend

- React 19 + TypeScript
- Vite
- Tailwind CSS
- xterm.js (web terminal attached to the local PTY/WebSocket)
- TanStack Query + Zustand
- Recharts (coverage/severity charts)
- Playwright for E2E

### Packaging

- `pipx install janus` / `uv tool install`
- Docker Compose for the demo lab
- Optional single-file Windows installer (MSIX or Inno Setup) in a later milestone

---

## 4. Process architecture

```text
┌──────────────────────────────┐
│  React UI (127.0.0.1 only)   │
│  dashboard + xterm terminal  │
└──────────────┬───────────────┘
               │ HTTPS/WSS + token
┌──────────────▼───────────────┐
│  janusd (FastAPI daemon)     │
│  API · WebSocket · auth      │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│  Agent Orchestrator          │
│  plan → policy → approve →   │
│  execute → observe → reflect │
└──────┬───────────┬───────────┘
       │           │
┌──────▼─────┐ ┌───▼──────────┐
│ Policy     │ │ Tool Gateway │
│ Engine     │ │ + Sandbox    │
│ scope/risk │ │ + egress     │
└──────┬─────┘ └───┬──────────┘
       │           │
┌──────▼───────────▼───────────┐
│ Audit · Evidence · Memory    │
└──────────────────────────────┘
```

Entry points:

- `janus` — headless CLI (scriptable)
- `janus tui` — full terminal UI
- `janus ui` — starts `janusd` + serves the React dashboard at `127.0.0.1:<port>`
- `janusd` — daemon only

The terminal is the primary interface. The React app is a local dashboard with an embedded terminal; it must bind to loopback only and require a per-session token.

---

## 5. Agent loop

Implement a deterministic state machine around the LLM:

```text
INTAKE → PLAN → POLICY_CHECK → (APPROVAL?) → EXECUTE → OBSERVE
      → RECORD → REFLECT → UPDATE_PLAN → ...
      → CLOSURE_GATES → REPORT
```

Requirements:

- **Planner** decomposes the engagement into phases, assets, and test cases from the approved matrix.
- **Policy check** runs before every tool call. It is pure code, not an LLM judgment.
- **Approval broker** issues single-use, expiring approval tokens; the executor refuses `INTRUSIVE` actions without a valid token.
- **Executor** runs tools only through the gateway, inside the sandbox, with timeouts and rate limits.
- **Observer** parses output into structured findings; raw output is stored as evidence.
- **Reflector** updates the plan, records decisions, and detects loops or stalled coverage.
- **Critic** independently reviews findings and coverage before closure and before report generation.
- **Kill switch** terminates the agent, child processes, and sandbox containers immediately.

Every step writes an audit event.

---

## 6. Safety enforcement (must be code, not prompt)

### 6.1 Authorization gate

- `RoE` schema validated on load; required fields include engagement ID, owner, authorization reference, scope, exclusions, window, allowed/prohibited techniques, rate limits, emergency contact, data handling.
- No valid RoE → `SAFE_MODE`: no network, no tool execution.
- RoE expiry is enforced in real time; expiry mid-run triggers a stop.
- Any scope amendment requires a new signed record; the UI shows the diff.

### 6.2 Scope guard

Implement at the network layer, not only in prompts:

- DNS resolution pinned per request; re-resolve and re-check on every connection.
- CIDR + domain + URL + cloud-account allow-lists.
- Block private ranges unless explicitly in scope; always block cloud metadata endpoints (`169.254.169.254`, `fd00:ec2::254`) unless a specific lab exception is recorded.
- Re-validate every HTTP redirect hop and every resolved IP.
- Route tool traffic through an egress proxy that enforces the scope.
- Block raw sockets and arbitrary outbound connections from sandboxed tools by default.
- Unit-test with DNS rebinding, redirect-to-outside, IPv6, and CDN cases.

### 6.3 Risk classifier

- Classify every tool and command as `PASSIVE`, `SAFE_ACTIVE`, `INTRUSIVE`, or `PROHIBITED`.
- Unknown commands default to `INTRUSIVE` and require approval; dangerous patterns default to `PROHIBITED`.
- Maintain a prohibited-pattern list (DoS, destructive writes, credential dumping, persistence, evasion, malware).
- The classifier must be conservative and fail closed.

### 6.4 Approval broker

- Approval request includes action, target, technique, risk, impact, rollback, alternatives, expiry.
- Single-use token, bound to the exact command hash, target, and engagement.
- Denied or expired tokens cannot be reused.
- Approvals are recorded in the audit log with operator identity and timestamp.
- The agent cannot approve itself or auto-approve after a timeout.

### 6.5 Sandbox

- Linux: Docker/Podman container with a non-root user, read-only root filesystem, dropped capabilities, seccomp/AppArmor, CPU/memory/time limits, and network access only through the scope proxy.
- Windows: WSL2/Docker Desktop container, or Windows Sandbox for intrusive work.
- Host execution is limited to an allow-list of read-only commands.
- No host filesystem mounts except a dedicated workspace and evidence directory.
- Intrusive work should run against a disposable VM/snapshot; document this in the UI.

### 6.6 Untrusted content

- Treat all target output as data.
- Strip/escape ANSI sequences and control characters before display.
- Never pass target text into a shell, template, or `eval`.
- Detect prompt-injection patterns and flag them; do not follow them.
- Keep an "untrusted content" boundary in the agent context; label tool output as untrusted.

### 6.7 Kill switch

- `/stop`, `Ctrl+C`, a TUI button, and an API endpoint.
- Terminates the agent loop, tool subprocesses, and sandbox containers within 1 second.
- Writes a final audit event and leaves evidence intact.
- `/resume` requires re-validation of scope and a fresh approval.

### 6.8 Audit and evidence

- Append-only JSONL, each entry hashed with the previous entry (hash chain).
- Evidence files encrypted at rest, SHA-256 manifest, immutable permissions.
- Redaction pipeline for secrets, tokens, cookies, keys, and PII.
- Export bundle for the client with redacted evidence and full audit trail.

---

## 7. Data model

Minimum tables:

```text
engagements(id, name, client, authorization_ref, status, starts_at, ends_at, created_at)
scope_assets(id, engagement_id, type, value, exclusions, created_at)
roe_versions(id, engagement_id, version, document_hash, signed_by, signed_at, payload_json)
runs(id, engagement_id, phase, status, started_at, ended_at, summary)
agent_steps(id, run_id, step_no, kind, plan_json, decision, created_at)
tool_invocations(id, run_id, tool, command_hash, risk_class, scope_check, approval_id, status, started_at, ended_at, output_hash)
approvals(id, engagement_id, action, target, risk, status, requested_at, decided_at, decided_by, token_hash, expires_at)
findings(id, engagement_id, run_id, title, severity, cvss_vector, cvss_score, confidence, status, description, impact, remediation, created_at)
finding_assets(finding_id, asset_id)
evidence(id, engagement_id, finding_id, kind, path, sha256, sensitivity, created_at)
memory_records(id, engagement_id, type, source, confidence, sensitivity, content, embedding_ref, created_at, ttl_days)
memory_embeddings(id, record_id, vector)
reports(id, engagement_id, format, path, sha256, gate_status, created_at)
audit_events(id, engagement_id, actor, action, target, payload_json, prev_hash, hash, created_at)
skills(id, version, domain, risk_class, manifest_json, enabled)
```

Indexes on `engagement_id`, `finding_id`, `created_at`, and `status`. Use migrations from day one.

---

## 8. API surface

REST (all require a local session token; loopback only):

```text
GET    /health
GET    /api/engagements
POST   /api/engagements
GET    /api/engagements/{id}
GET    /api/engagements/{id}/scope
POST   /api/engagements/{id}/scope/validate
GET    /api/engagements/{id}/status
GET    /api/engagements/{id}/findings
GET    /api/engagements/{id}/coverage
GET    /api/engagements/{id}/approvals
POST   /api/approvals/{id}/decision
POST   /api/engagements/{id}/stop
POST   /api/engagements/{id}/resume
GET    /api/engagements/{id}/evidence/{evidence_id}
GET    /api/engagements/{id}/reports
POST   /api/engagements/{id}/reports
GET    /api/memory?engagement_id=...
DELETE /api/memory/{id}
WS     /ws/terminal
WS     /ws/events
```

WebSocket events: `agent.step`, `agent.message`, `policy.blocked`, `approval.requested`, `tool.started`, `tool.output`, `finding.created`, `gate.updated`, `run.stopped`, `report.ready`.

---

## 9. Terminal UI (Textual)

Layout:

```text
┌ JANUS ─ ENG-2026-001 ─ PHASE 3/8 ─ SCOPE OK ─ COVERAGE 42% ─ 7 findings ┐
│ conversation / command input                                           │
│ ...                                                                    │
├──────────────────────────┬─────────────────────────────────────────────┤
│ Findings (7)             │ Approvals (1 pending)                       │
│ critical 1  high 2 ...   │ APPROVAL REQUIRED ...                       │
├──────────────────────────┴─────────────────────────────────────────────┤
│ gates: [1 ✓] [2 …] [3 ] [4 ]   next: validate auth bypass              │
└────────────────────────────────────────────────────────────────────────┘
```

Requirements:

- Streaming agent output.
- Slash commands from the runtime prompt.
- Approval modal with explicit APPROVE/DENY.
- Finding detail view with redacted evidence.
- Gate tracker.
- Stop button and keyboard shortcut.
- Works over SSH; degrades gracefully without color.
- `--no-color`, `--json` for automation.

---

## 10. React dashboard

Views:

1. **Engagement** — RoE summary, scope, window, status, kill switch.
2. **Terminal** — xterm.js connected to `/ws/terminal`; full TUI-equivalent commands.
3. **Findings** — filter by severity/status/asset; detail drawer; evidence viewer (redacted).
4. **Coverage** — matrix by asset × test class; gate progress.
5. **Approvals** — pending/history; approve/deny with confirmation.
6. **Memory** — search, inspect, export, delete; shows engagement isolation.
7. **Reports** — generate, preview, download Markdown/PDF/JSON; gate status.
8. **Audit** — timeline, hash-chain verification, export.

Design: dark, dense, terminal-inspired; accessible contrast; keyboard-first. Bind to `127.0.0.1`; generate a random session token on startup; strict CSP; no external telemetry; no CDN dependencies.

---

## 11. Memory ("Hermes-style")

Implement persistent memory with four layers:

- **Working:** current plan and context.
- **Episodic:** runs, decisions, approvals, tool calls, timeline.
- **Semantic:** assets, findings, relationships, embeddings.
- **Procedural:** skills and lessons learned.

Rules:

- Every record is scoped to an engagement.
- Verified/likely/unverified confidence labels.
- Secrets are never stored in plaintext; store vault references.
- Redaction before write and before display.
- Cross-engagement retrieval is opt-in and sanitized.
- TTL and deletion per RoE.
- Memory never grants authorization; scope is always re-validated.
- Provide a memory inspector and export/delete API.
- If the user's "Hermes" refers to a specific existing system, provide an adapter interface so its storage backend can be plugged in without changing the agent.

---

## 12. Skills engine

Each skill is a YAML manifest plus an optional Python handler:

```yaml
id: web-auth-session
version: 1.0.0
domain: offensive
phase: 4
risk_class: SAFE_ACTIVE
description: Review authentication and session management controls.
preconditions:
  - valid_scope
  - asset_reachable
approval_required: false
tools:
  - http-client
  - browser-sandbox
stop_conditions:
  - account_lockout_risk
  - production_impact
output_schema: finding.v1
references:
  - OWASP-WSTG-AUTH
```

Ship skill families:

- Offensive: passive OSINT, network/service enumeration, web app, API, AD/Windows review, Linux privesc review, cloud config, container/CI-CD, attack-path analysis, controlled validation.
- Defensive: hardening benchmarks, patch management, detection engineering, log review, IR readiness, threat modeling, secure architecture, backup resilience, remediation planning.
- Reporting: executive/technical report generation, CVSS, ATT&CK mapping, coverage matrix, closure attestation.
- Meta: scope validation, RoE compliance, approvals, evidence custody, critic.

The skill loader validates manifests, enforces risk class, and refuses unregistered skills. Skills cannot override policy.

---

## 13. Four-Gate closure state machine

Implement as code with persisted state:

```text
GATE_1_COVERAGE
GATE_2_VALIDATION
GATE_3_CLEAN_SWEEP
GATE_4_REGRESSION_REVIEW
COMPLETE | COMPLETE_WITH_ACCEPTED_RISK | INCOMPLETE
```

Rules:

- Gates are sequential.
- Any new verified finding resets Gates 3 and 4.
- Gate 1 requires a complete test matrix with N/A justifications.
- Gate 2 requires two independent reproductions per finding and evidence links.
- Gate 3 requires a full re-run with different tooling/heuristics and zero new findings.
- Gate 4 requires regression of all findings plus critic sign-off.
- The report endpoint rejects `COMPLETE` unless all gates are green.
- The UI must show gate evidence and blockers.

---

## 14. Reporting

- Jinja2 templates → Markdown → PDF (WeasyPrint) + JSON.
- Languages: Arabic (RTL), French, English; selectable per engagement.
- Findings include CVSS 4.0, ATT&CK mapping, evidence references, reproduction steps, impact, remediation.
- Executive summary is non-technical and business-focused.
- Coverage matrix and limitations are mandatory.
- Closure wording must match the runtime prompt exactly; never claim absolute security.
- Redact secrets and personal data.
- Every report has a SHA-256 hash and is recorded in the audit log.

---

## 15. Windows and Linux requirements

### Windows 11

- PowerShell 7 detection; UTF-8 output; long-path handling.
- UAC elevation through a helper that prompts the operator; never store admin credentials.
- Support Windows Sandbox / WSL2 for tool execution.
- Test on Windows 11 23H2+.
- Installer/uninstaller; no background service by default.

### Linux

- Ubuntu 22.04/24.04 and Debian 12 primary targets.
- `sudo` elevation with explicit confirmation; never modify sudoers.
- Docker/Podman sandbox detection with a clear fallback message.
- Systemd unit optional, user-level by default.
- Respect XDG paths and file permissions (0600 for config/secrets).

### Both

- No telemetry.
- Offline mode works for planning and reporting.
- Graceful degradation when Docker is unavailable.
- Clear error messages with remediation steps.

---

## 16. Testing and acceptance criteria

### Automated tests

- Unit: RoE validation, scope guard (DNS rebinding, redirects, IPv6, CIDR edges), risk classifier, approval tokens, redaction, hash chain, gate state machine.
- Integration: tool gateway with a mock target; sandbox egress blocking; memory isolation; report generation.
- E2E: CLI/TUI flow and React flow against the Docker lab.
- Security tests: prompt injection in HTTP responses, command injection via tool output, path traversal in evidence storage, token replay, CSRF.

### Acceptance criteria

1. Out-of-scope target is blocked at the network layer; test proves no packet leaves.
2. `INTRUSIVE` action without approval is refused and audited.
3. Kill switch stops agent + child processes + containers within 1 second.
4. Prompt injection in a target response does not change agent behavior.
5. A finding without evidence cannot enter the report.
6. `COMPLETE` report is impossible while any gate is open.
7. Memory from engagement A is not visible in engagement B by default.
8. Secrets never appear in logs, terminal output, or reports.
9. Demo lab produces a report with findings, coverage, and four-gate attestation.
10. App runs on Windows 11 and Ubuntu 24.04.

---

## 17. Milestones

1. **Foundation:** repo, config, DB, RoE schema, FastAPI health, CLI skeleton, audit log.
2. **Safety core:** scope guard, risk classifier, approval broker, kill switch, sandbox gateway, tests.
3. **Agent core:** orchestrator, planner, tool registry, memory, streaming TUI chat.
4. **Skills + findings:** skill loader, 6–8 initial skills, finding lifecycle, evidence pipeline.
5. **Closure + reporting:** four-gate state machine, critic, report templates, PDF/JSON.
6. **React UI:** terminal, dashboard, findings, approvals, coverage, reports.
7. **Packaging + demo:** Docker lab, installers, docs, E2E, security review.

Each milestone must include tests and documentation. Do not defer safety controls to the end.

---

## 18. Non-goals

- No malware, ransomware, wipers, C2, or persistence.
- No exploit development or weaponization.
- No DoS/DDoS capability.
- No stealth/evasion or anti-forensics.
- No attacking third parties or the public internet at large.
- No bypassing the authorization gate for "demo" purposes.
- No cloud service that receives client data by default.

---

## 19. Documentation

- `docs/architecture.md` — components, data flow, trust boundaries.
- `docs/threat-model.md` — STRIDE for the platform itself; prompt injection, tool abuse, scope bypass, evidence tampering.
- `docs/safety.md` — authorization model, approvals, stop conditions, incident procedure.
- `docs/operations.md` — install, configure RoE, run demo, backup, upgrade, uninstall.
- `README.md` — quick start, legal notice, screenshots.

---

## 20. Definition of done

- All acceptance criteria pass in CI on Windows and Linux.
- Demo lab produces a complete report.
- Safety controls are enforced by tests, not just prompts.
- A security review confirms no path to out-of-scope action without an explicit, recorded approval.
- The operator can inspect and delete all stored data.
- The product clearly states: authorized testing only.

---

## 21. Final instruction to the coding agent

Build the smallest end-to-end vertical slice first: **RoE → scope guard → approval → sandboxed tool → evidence → finding → report**. Then expand skills and UI.

Never trade safety for demo speed. If a feature cannot be made safe, do not ship it; document the limitation and propose a safer alternative.
