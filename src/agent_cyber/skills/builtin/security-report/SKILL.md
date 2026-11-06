---
id: security-report
name: Security Report Writer
description: Turn assessment notes, findings, and evidence into a clear professional security report with severity, impact, remediation, coverage, and closure status.
version: 1.0.0
triggers:
  - report
  - تقرير
  - rapport
  - findings
  - تقييم
---

# Security Report Writer

Use this skill when the operator asks for a report, an assessment summary, a findings document, or a client-ready deliverable.

## Inputs to establish

- Engagement name, client/owner, and authorization reference
- Scope, exclusions, and testing window
- Methodology and standards used
- Findings with evidence references
- What was **not** tested and why
- Current closure status (coverage, validation, clean sweep, regression)

If an input is missing, mark it as `Not provided` rather than inventing it.

## Report structure

1. **Cover** — title, engagement ID, client, classification, date, authorization reference
2. **Executive summary** — 5–8 short paragraphs or bullets for a non-technical reader: what was assessed, the most important risks, the overall posture, and the top three actions
3. **Scope and exclusions** — assets, time window, constraints, contacts
4. **Methodology** — standards, phases, tools/technique categories, evidence handling
5. **Risk overview** — counts by severity, affected assets, a short trend/priority statement
6. **Findings** — one section per finding using the schema below
7. **Attack narrative** — only validated chains; clearly separate confirmed from hypothetical
8. **Defensive recommendations** — prioritized, owner-oriented, with verification steps
9. **Coverage and limitations** — test matrix summary, gaps, N/A justifications
10. **Closure status** — four-gate status and exact wording
11. **Residual risk** — what remains unknown or unverified
12. **Appendices** — evidence index, timeline, glossary

## Finding schema

```markdown
### JANUS-001 — Short, specific title

- **Severity:** Critical / High / Medium / Low / Info
- **CVSS 4.0:** `CVSS:4.0/...` (score: X.X)
- **Confidence:** Verified / Likely / Unverified
- **Affected assets:** ...
- **Status:** Open / Fixed / Accepted risk / False positive

**Description**
What the issue is, in plain language.

**Evidence**
Evidence IDs, redacted excerpts, timestamps, and reproduction context.

**Reproduction**
Numbered, minimal, reversible steps. Do not include destructive actions.

**Impact**
Technical impact and business impact. Explain who can do what, and why it matters.

**Remediation**
Specific fix, configuration change, or compensating control. Include verification steps.

**References**
Standards, vendor guidance, ATT&CK technique IDs.
```

## Severity rules

- Use CVSS 4.0 plus business context. Never inflate a score to make a report look stronger.
- A finding without evidence is an **observation**, not a confirmed finding.
- Duplicate findings must be merged with a shared root cause.
- If exploitability is unverified, say so and lower confidence — not necessarily severity.

## Closure wording

Only use absolute closure language when the four gates are actually complete:

> "No verified findings within the agreed scope and methodology as of `<date>`. This is not a guarantee of absolute security."

Never write "100% secure", "no vulnerabilities exist", or "unhackable".

## Quality checklist

- [ ] Every finding has an evidence reference
- [ ] Severity is justified on the page
- [ ] Reproduction steps are safe and reproducible
- [ ] Remediation is actionable and owned
- [ ] Coverage and limitations are explicit
- [ ] Secrets and personal data are redacted
- [ ] Counts match the findings list
- [ ] Executive summary is consistent with the technical body
- [ ] Closure wording matches the gate state
