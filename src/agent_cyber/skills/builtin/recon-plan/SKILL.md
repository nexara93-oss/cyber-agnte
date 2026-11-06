---
id: recon-plan
name: Authorized Recon Plan
description: Build a scoped, rate-limited reconnaissance plan for an authorized engagement, with approval gates and stop conditions.
version: 1.0.0
triggers:
  - recon
  - enumeration
  - scope
  - استطلاع
  - خطة
---

# Authorized Recon Plan

Use this skill when the operator needs a reconnaissance or enumeration plan. This skill produces a plan, not live scanning.

## Required inputs

- Written authorization reference and asset owner
- In-scope domains, URLs, CIDRs, cloud accounts, and accounts
- Exclusions and third-party dependencies
- Testing window and rate limits
- Emergency contact and escalation path
- Defensive coordination requirements

If any required input is missing, stop and list exactly what is needed.

## Plan structure

### Phase 0 — Scope validation

- Resolve every target and confirm it is inside the approved scope.
- Check redirects, CDN origins, IPv6, and wildcard DNS.
- Identify third-party services that must not be touched.
- Confirm the kill switch and approval channel.

### Phase 1 — Passive discovery

- Public DNS, certificate transparency, search engines, public code/metadata.
- No packets to the target beyond normal public lookups.
- Record source, timestamp, and confidence for every asset.

### Phase 2 — Safe active enumeration

- Asset discovery, service/version identification, TLS configuration.
- Rate limits, timeouts, and concurrency caps from the RoE.
- Every target re-checked against scope before the request.

### Phase 3 — Validation preparation

- Turn observations into candidate findings with evidence.
- Identify which candidates need intrusive validation.
- Request approval before any exploitation or credential use.

## Output table

```markdown
| Step | Activity | Target | Technique category | Risk | Approval | Stop condition | Output |
|---|---|---|---|---|---|---|---|
```

## Rules

- Prefer passive over active, and active over intrusive.
- No public-internet scanning, no third-party targets, no stealth unless explicitly authorized.
- Include a "do not test" list.
- Include an abort procedure and evidence-preservation steps.
- The plan must fit the testing window and rate limits.
- A plan is not authorization; the signed RoE is.
