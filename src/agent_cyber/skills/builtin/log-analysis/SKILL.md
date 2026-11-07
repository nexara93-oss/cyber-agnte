---
id: log-analysis
name: Security Log Analysis
description: Analyze authentication, endpoint, firewall, and application logs for suspicious activity, build a timeline, and propose containment and detection improvements.
version: 1.0.0
triggers:
  - log
  - logs
  - incident
  - timeline
  - تحليل
  - سجلات
---

# Security Log Analysis

Use this skill when the operator attaches logs, alert exports, or a SIEM query result and needs an investigation summary.

## Method

1. **Establish context** — log source, time range, timezone, host roles, expected traffic, and known changes.
2. **Normalize** — map fields to a common schema: timestamp, source, user, action, result, src/dst IP, host, process, hash.
3. **Baseline** — identify normal volumes and rare events; compare against the same time window on other days if available.
4. **Build a timeline** — first seen, last seen, count, and sequence for each suspicious entity.
5. **Test hypotheses** — benign explanation, misconfiguration, compromised account, insider, automated scanner. State what evidence would confirm or reject each.
6. **Map to ATT&CK** — only when the behavior is evidenced, not guessed.
7. **Recommend** — containment, investigation steps, detection rule ideas, and missing telemetry.

## Output

- **Summary** — what happened, confidence, and what is still unknown
- **Timeline table** — timestamp, host, user, event, evidence
- **Entities** — accounts, hosts, IPs, processes, hashes
- **Indicators** — with confidence and false-positive notes
- **Hypotheses** — supported / rejected / open
- **Containment** — least disruptive first, with impact and rollback
- **Detection gaps** — telemetry or rule improvements
- **Evidence handling** — preserve originals, hash them, do not modify logs

## Rules

- Never alter or delete logs.
- Do not accuse a person; describe behavior and confidence.
- Distinguish correlation from causation.
- Redact credentials, tokens, and personal data in the report.
- If the evidence suggests an active incident, recommend escalation immediately.
- If the log window is too narrow, say so; do not overstate conclusions.
