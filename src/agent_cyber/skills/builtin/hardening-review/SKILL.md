---
id: hardening-review
name: Windows & Linux Hardening Review
description: Review Windows and Linux configuration against CIS-style controls, identify gaps, and produce a prioritized, read-only remediation plan.
version: 1.0.0
triggers:
  - hardening
  - cis
  - benchmark
  - تقوية
  - إعدادات
---

# Windows & Linux Hardening Review

Use this skill when the operator attaches configuration exports, `auditpol` output, `secedit` exports, `sshd_config`, systemd units, sysctl values, firewall rules, or inventory data.

## Review areas

### Windows

- Account and authentication policy (MFA, lockout, privileged groups)
- Local administrator and service-account hygiene
- UAC, Defender, firewall, exploit protection
- Audit policy and PowerShell logging
- SMB, WinRM, RDP exposure
- Patch level and unsupported software
- BitLocker and credential protection

### Linux

- SSH configuration and key management
- sudoers and privileged group membership
- SUID/SGID and file capabilities inventory
- systemd service sandboxing and permissions
- Kernel and package patch level
- Firewall and listening services
- Auditd and centralized logging
- Mount options, cron, and secrets on disk

## Output table

```markdown
| ID | Platform | Control | Current state | Target | Severity | Effort | Verification |
|---|---|---|---|---|---|---|---|
```

Then include:

- **Quick wins** — low effort, high risk reduction
- **Structural fixes** — require change management
- **Compensating controls** — when the ideal fix is not feasible
- **Exceptions** — documented risk acceptance with owner and expiry
- **Verification commands** — read-only checks the operator can run

## Rules

- This is a read-only review. Do not change configurations.
- Do not recommend disabling security controls to make a test pass.
- Separate compliance gaps from exploitable exposure.
- Note when the attached data is incomplete or stale.
- Prefer vendor and CIS/STIG references over generic advice.
- Every recommendation needs a verification step.
