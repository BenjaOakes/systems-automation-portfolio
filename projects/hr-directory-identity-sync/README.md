# HR Directory Identity Sync

Operational posture: `PROVIDER-READY / MOCK PROVIDERS`. Planning and dry-run are the defaults; the included execute path mutates only mock HR, Entra, and AD providers. No live connector is included.

## Problem and use case

HR systems describe employment and organizational policy, while AD and Entra hold operational identity state. A safe synchronization process needs normalized records, deterministic matching, configurable policy, complete collection, collision checks, bounded plans, post-step verification, and an audit journal.

This project is based on real-world HR-to-directory synchronization problems I have worked on, including HR/HCM integrations such as UKG and hybrid Active Directory / Microsoft Entra identity lifecycle automation. The public implementation uses generic provider contracts and synthetic data; it does not connect to UKG, Graph, AD, or an organization-specific policy.

This project is modeled around real-world HR-to-directory identity synchronization, but uses provider contracts and synthetic data so it can be adapted to another organization’s HR and directory systems. It is deliberately generic and does not publish any source organization’s policy.

The intended audience is identity engineers, HRIS/integration developers, directory administrators, platform engineers, and reviewers of high-impact reconciliation.

## What it demonstrates

- HR/HCM ingestion and normalization, including employment status and invalid-input reporting.
- Identity matching by employee ID, then normalized email/alias fallback, with duplicate and ambiguous matches blocked.
- Hybrid AD/Entra concepts: records with the same employee ID are merged for planning while system targets remain visible.
- Policy-driven UPN, primary-email, department-group, brand, employee-type, managed-attribute, and manager handling.
- Collision detection, missing-manager review, complete-collection safety, dry-run planning, explicit mock execute, retries, post-step verification, audit/reporting, and second-run idempotency.

## Architecture and configuration

The HR provider returns normalized employee-shaped mappings plus a completeness flag. Directory providers return identity records plus completeness. The policy calculates desired attributes; the reconciliation engine matches records and emits `Create`, `Update`, `Disable`, or `NoChange` actions with `Blocked` and `ReviewRequired` states. The reporting layer serializes a plan and optional mutation journal.

`config/identity-policy.example.json` and the YAML templates show where fictional brand domains, department groups, employee-type behavior, managed attributes, tenant/application references, certificate references, AD search bases, and execution thresholds belong. Secrets never belong in committed config; use a certificate store, managed identity, SecretManagement, Windows Credential Manager, or an approved vault.

## Runnable synthetic example

From the project directory:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m hr_directory_sync.cli --employees examples/employees.example.csv --directory examples/directory.example.json --policy config/identity-policy.example.json
python -m hr_directory_sync.cli --employees examples/employees.example.csv --directory examples/directory.example.json --policy config/identity-policy.example.json --execute --output .\output\execution.json
python -m unittest discover -s tests -v
```

The fixture includes a new hire, no-change employee, department/brand changes, a termination, duplicate HR data, an ambiguous email match, a UPN collision, a missing manager, and invalid input. The first command is a plan; its finding-bearing rows return exit `1`. `--execute` is a mock-only demonstration and writes no provider outside the process.

## Provider development

Another engineer implementing a real environment would provide:

1. An HR/HCM adapter with paged `list_employees()` returning employee ID, names, work email, department, brand, employee type, manager ID, employment status, and a truthful completeness flag.
2. An Entra adapter with complete paged identity reads and `apply(ChangeItem)` / `verify(ChangeItem)` support for the selected managed attributes.
3. An AD adapter with complete searches for employee ID, UPN, mail/proxy addresses, enabled state, manager, and selected managed attributes, plus the same apply/verify contract.

Adapters own authentication, API/LDAP pagination, retry classification, rate limits, permission checks, provider-specific transaction/rollback design, and sensitive-field handling. Expected permissions vary by implementation: HR read access, least-privilege Entra directory read/write access for approved attributes, and narrowly scoped AD read/write rights. The core must not guess when identities are ambiguous or collections are incomplete. See [docs/provider-development.md](docs/provider-development.md).

## Safety, testing, and limitations

The project cannot prove a real directory-wide collision without a complete provider snapshot. Manager review does not invent a manager, and a partial HR or directory feed fails before planning. Tests cover normalization, policy, hybrid merging, matching, collisions, completeness, dry-run, mock execution, verification, and idempotency. HR and directory records are sensitive; keep real data outside fixtures and reports. See [docs/safety.md](docs/safety.md).
