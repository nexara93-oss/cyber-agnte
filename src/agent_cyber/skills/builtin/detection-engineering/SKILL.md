---
id: detection-engineering
name: Detection Engineering
description: Turn findings and threat behavior into concrete telemetry requirements, detection rules, test cases, and false-positive handling.
version: 1.0.0
triggers:
  - detection
  - sigma
  - siem
  - telemetry
  - كشف
---

# Detection Engineering

Use this skill when the operator wants to detect a behavior, improve a SIEM rule,
or verify that a finding would be caught.

## Method

1. **Describe the behavior** — actor, action, target, outcome, and telemetry source.
2. **Map to ATT&CK** — technique and sub-technique, only when evidenced.
3. **Identify telemetry** — which logs/events are required, at which granularity.
4. **Write the detection logic** — Sigma-like pseudo-rule or platform query.
5. **Define false positives** — expected benign patterns and exclusions.
6. **Define test cases** — positive, negative, and evasion variants.
7. **Set response guidance** — severity, triage steps, escalation.

## Output

```markdown
## Detection: <name>
- Behavior:
- ATT&CK:
- Telemetry:
- Logic:
- False positives:
- Test cases:
- Response:
- Coverage gaps:
```

## Rules

- Do not propose detection that relies on data the organization does not collect.
- Prefer high-signal, behavior-based logic over brittle string matches.
- Include a safe test plan; do not execute attacks on production.
- Avoid collecting credentials or personal data unnecessarily.
- State the confidence and known blind spots.
- A rule is not complete without false-positive handling and a test case.
