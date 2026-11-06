---
id: windows-ad-review
name: Windows & Active Directory Review
description: Read-only review of Windows and Active Directory configuration, privileged access, delegation, GPOs, trusts, and logging.
version: 1.0.0
triggers:
  - active directory
  - windows
  - ad
  - domain
  - ويندوز
---

# Windows & Active Directory Review

Use this skill when the operator provides AD inventory, GPO exports, privileged
group membership, `secedit` output, BloodHound-style data, or Windows
configuration notes.

## Review areas

### Identity and authentication

- Privileged groups: Domain Admins, Enterprise Admins, Schema Admins, Account
  Operators, Backup Operators, and nested memberships
- Service accounts, SPNs, password age, and interactive logon rights
- MFA and conditional access for administrative access
- Kerberos policy: ticket lifetime, clock skew, encryption types
- LAPS/Windows LAPS coverage for local administrators

### Delegation and trusts

- Unconstrained, constrained, and resource-based constrained delegation
- Trust direction, transitivity, SID filtering, and forest boundaries
- ACL exposure on domain objects and adminSDHolder
- Certificate services and enrollment permissions

### Policy and hardening

- GPO precedence and conflicting settings
- SMB signing, LDAP signing/channel binding, NTLM restrictions
- PowerShell logging, script block logging, and transcription
- WinRM, RDP, and remote access exposure
- Patch level and unsupported operating systems
- Defender/EDR coverage and exclusions

### Monitoring

- Domain controller audit policy
- Kerberos and authentication event coverage
- Privileged group change alerts
- Lateral movement detection opportunities

## Output

```markdown
| ID | Area | Observation | Evidence | Risk | Confidence | Remediation |
|---|---|---|---|---|---|---|
```

Include:

- Attack paths that are **evidenced** (not speculative)
- Tiering/segmentation recommendations
- Privileged access cleanup plan
- Detection opportunities mapped to ATT&CK
- Verification steps for each fix

## Rules

- Read-only review. Do not change AD, GPOs, ACLs, or group membership.
- Do not request or use real credentials.
- Do not provide credential-dumping, Kerberoasting, or coercion instructions.
- Distinguish a configuration weakness from a confirmed exploitable path.
- Redact usernames, hashes, and sensitive identifiers in the report.
