---
id: vuln-triage
name: Vulnerability Triage
description: Validate, deduplicate, score, and prioritize security findings by exploitability, exposure, business impact, and compensating controls.
version: 1.0.0
triggers:
  - triage
  - prioritize
  - أولويات
  - ثغرات
  - vulnerability
---

# Vulnerability Triage

Use this skill when the operator provides scanner output, a findings list, or patch backlog and needs a defensible priority order.

## Triage pipeline

1. **Normalize** — one row per root cause, not one row per scanner alert.
2. **Validate** — confirm the finding with evidence or mark it `Potential`. Remove duplicates and false positives.
3. **Score** — CVSS 4.0 base score, then adjust for:
   - internet exposure vs internal-only
   - authentication/authorization required
   - user interaction required
   - known exploitation in the wild
   - compensating controls (WAF, segmentation, EDR, MFA)
4. **Business impact** — confidentiality, integrity, availability, safety, regulatory, and reputational impact.
5. **Priority** — assign `P0`–`P3` with a short rationale.
6. **Remediation path** — patch, configuration change, compensating control, or accept with owner and expiry.

## Priority guidance

| Priority | Meaning | Target |
|---|---|---|
| P0 | Actively exploited or trivially exploitable, high business impact | Immediate / same day |
| P1 | Confirmed high impact, realistic path | 7 days |
| P2 | Medium impact or requires significant preconditions | 30 days |
| P3 | Low impact, hardening, defense in depth | 90 days |

These are defaults; the RoE or client policy may override them.

## Output table

```markdown
| ID | Finding | Asset | Evidence | CVSS | Exposure | Exploitability | Business impact | Priority | Owner | Due |
|---|---|---|---|---|---|---|---|---|---|---|
```

Then add:

- **Top 5 actions** — what to fix first and why
- **Accepted risks** — owner, reason, expiry
- **Validation plan** — how to prove each fix worked
- **Data gaps** — what could change the priority if known

## Rules

- Do not invent CVSS vectors or exploit status.
- Distinguish `Confirmed`, `Likely`, and `Potential`.
- A scanner "critical" is not automatically a business-critical finding.
- Prefer root-cause fixes over alert-by-alert patching.
- Record uncertainty explicitly; it is part of the triage.
