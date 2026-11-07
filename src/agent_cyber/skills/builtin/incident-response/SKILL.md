---
id: incident-response
name: Incident Response Advisor
description: Guide an incident from detection through containment, eradication, recovery, and lessons learned using a NIST-style lifecycle, with evidence preservation.
version: 1.0.0
triggers:
  - incident response
  - incident
  - containment
  - حادث
  - استجابة
---

# Incident Response Advisor

Use this skill when the operator reports a suspected compromise, active intrusion, ransomware event, account takeover, or data exposure.

## Lifecycle

### 1. Preparation

- Confirm roles, escalation contacts, legal/privacy involvement, and communication channels.
- Establish what evidence must be preserved before any cleanup.
- Confirm authorization for containment actions.

### 2. Detection and analysis

- Build a timeline from logs and alerts.
- Identify affected hosts, accounts, data, and business services.
- Determine patient zero, initial access vector, and persistence (if evidenced).
- State confidence and unknowns.

### 3. Containment

- Prefer the least disruptive containment that stops spread.
- Options: isolate host, disable account, block indicator, revoke sessions, rotate credentials.
- Record every action, time, actor, and expected impact.
- Preserve memory/disk evidence before shutdown when feasible and authorized.

### 4. Eradication

- Remove the root cause, not just the symptom.
- Patch, rebuild, rotate secrets, remove unauthorized access.
- Verify that persistence is gone.

### 5. Recovery

- Restore from trusted backups, monitor closely, and validate business functionality.
- Define exit criteria and a heightened-monitoring period.

### 6. Lessons learned

- What worked, what failed, detection gaps, control gaps, and owners.
- Update playbooks and detections.

## Output

- Situation summary and confidence
- Timeline
- Affected assets/data
- Immediate actions (with impact and rollback)
- Evidence preservation checklist
- Open questions and escalation
- Recovery and monitoring plan
- Lessons-learned template

## Rules

- Never destroy evidence to "clean up" faster.
- Do not contact attackers or pay ransoms without legal/executive direction.
- Do not make public statements; route communications to the designated owner.
- Separate confirmed facts from hypotheses.
- If there is risk to life, safety, or critical infrastructure, escalate immediately.
