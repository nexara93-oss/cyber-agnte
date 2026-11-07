---
id: linux-security-review
name: Linux Security Review
description: Read-only review of Linux accounts, sudo, SSH, services, kernel exposure, containers, and logging, with prioritized hardening and verification.
version: 1.0.0
triggers:
  - linux
  - ubuntu
  - debian
  - sudo
  - لينكس
---

# Linux Security Review

Use this skill when the operator attaches configuration files, inventory,
`ss -tulpn` output, systemd units, sudoers, audit logs, or a host description.

## Review areas

### Accounts and access

- UID 0 accounts and duplicate UIDs
- sudoers rules, aliases, and NOPASSWD entries
- SSH authorized keys, root login, password auth, and agent forwarding
- PAM configuration and password policy
- Service accounts and shell assignments

### Host hardening

- SUID/SGID binaries and file capabilities
- Writable service binaries, units, and PATH issues
- Cron/at jobs and systemd timers
- Kernel parameters and mandatory access control (SELinux/AppArmor)
- Mount options (`noexec`, `nosuid`, `nodev`) for sensitive paths
- Listening services and firewall exposure
- Patch level and EOL packages

### Containers and orchestration

- Privileged containers, host mounts, and namespace sharing
- Docker socket exposure
- Kubernetes service account and RBAC exposure
- Image provenance and secret handling

### Logging and detection

- auditd rules and log retention
- sudo, SSH, authentication, and service logs
- Forwarding to a central collector
- Detection coverage for privilege escalation and persistence

## Output

```markdown
| ID | Area | Observation | Evidence | Risk | Confidence | Remediation | Verify |
|---|---|---|---|---|---|---|---|
```

Include:

- Quick wins and structural fixes
- Compensating controls where immediate change is unsafe
- A read-only verification command for each recommendation
- Coverage gaps and assumptions

## Rules

- Read-only review. Do not modify sudoers, SSH, PAM, systemd, or firewall rules.
- Do not provide exploit code, rootkit, persistence, or evasion guidance.
- Do not exfiltrate credentials or private keys; redact them.
- Distinguish hardening gaps from confirmed privilege-escalation paths.
- Test recommendations in a lab before production.
