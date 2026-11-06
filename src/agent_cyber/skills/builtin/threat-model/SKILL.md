---
id: threat-model
name: Threat Model
description: Build a STRIDE-based threat model from an architecture description, data-flow diagram, or code/document excerpts, with trust boundaries and mitigations.
version: 1.0.0
triggers:
  - threat model
  - stride
  - architecture
  - threat
  - تهديدات
---

# Threat Model

Use this skill when the operator describes a system, attaches an architecture diagram, or asks what could go wrong.

## Process

1. **Define the system** — purpose, users, data, components, dependencies, deployment model.
2. **Draw the data flow** — external entities, processes, data stores, flows, and trust boundaries.
3. **Ask STRIDE questions** for every element and flow:
   - **Spoofing** — can identity be forged?
   - **Tampering** — can data or code be modified?
   - **Repudiation** — can an action be denied without evidence?
   - **Information disclosure** — can data leak?
   - **Denial of service** — can availability be degraded?
   - **Elevation of privilege** — can a lower privilege become higher?
4. **Rate** — likelihood, impact, existing controls, and confidence.
5. **Mitigate** — preventive, detective, and corrective controls, with owner and verification.
6. **Validate** — list assumptions and the tests that would confirm them.

## Output

- System summary and scope
- Data-flow / trust-boundary diagram (Mermaid is fine)
- Threat table:

```markdown
| ID | Element | STRIDE | Threat | Likelihood | Impact | Controls | Residual risk | Mitigation |
|---|---|---|---|---|---|---|---|---|
```

- Top risks with business context
- Assumptions and open questions
- Recommended validation activities (no live exploitation without authorization)

## Rules

- Model the system as described; do not invent components.
- Separate threats from vulnerabilities and from confirmed findings.
- Include insider, supply-chain, and misconfiguration scenarios where relevant.
- Do not provide malware, DoS, or evasion playbooks; describe risk and mitigation.
- Revisit the model when architecture or data flows change.
