# Systems Automation Portfolio

I’m a Systems Engineer focused on automation, identity, infrastructure, and making operational work safer and more repeatable. I enjoy taking work that normally lives in a collection of scripts, manual checks, and provider-specific assumptions and turning it into something deterministic, reviewable, and easier for the next engineer to operate.

This portfolio is where I explore identity lifecycle automation, Microsoft 365 / Entra, infrastructure, REST/API integrations, monitoring, security investigations, and reliable workflows using Python, PowerShell, and TypeScript.

## Background

My engineering work has involved real operational problems across UKG and other HR/HCM systems, Microsoft Entra ID (formerly Azure AD), Active Directory, Microsoft 365, Exchange Online, Microsoft Graph, Intune, SharePoint, and ITSM/CMDB integrations.

The problem categories represented here include HR-driven identity lifecycle automation, hybrid identity synchronization, UPN and primary-email migrations, employee offboarding workflows, Microsoft 365 administration, group reconciliation, domain and certificate monitoring, security investigations, and API integrations. The recurring work is not just moving data between systems; it is handling incomplete collections, ambiguous identities, retries, approvals, privacy, verification, and safe recovery.

Many of these projects grew from problems I have solved in real operational environments. The public versions have been redesigned to remove organization-specific configuration, credentials, identities, internal policy, and production data while preserving the engineering patterns that make the automation useful. They are intentionally generalized and synthetic; not every public implementation is a copy of an original production script.

## Featured projects

### [hr-directory-identity-sync](projects/hr-directory-identity-sync/README.md)

This project is based on experience building HR-driven identity automation involving UKG/HR systems and hybrid Active Directory / Microsoft Entra environments. The public implementation demonstrates HR normalization, identity matching, UPN/email policy, hybrid identity reconciliation, department and brand policy, collision detection, manager review, verification, reporting, and idempotency through generic provider contracts and synthetic data.

### [identity-address-migration-planner](projects/identity-address-migration-planner/README.md)

This project models the planning side of larger UPN and primary-email migrations. It turns brand and department policy, collision detection, alias preservation, deterministic planning, and review/block states into an offline proposal before a live directory or messaging change is considered.

### [idempotent-identity-workflow-engine](projects/idempotent-identity-workflow-engine/README.md)

This is a generic workflow pattern based on high-risk identity lifecycle work such as employee offboarding. It demonstrates phased execution, durable state, retries, post-step verification, protected identities, preview, `-WhatIf`, rollback/recovery metadata, and provider boundaries. The public project deliberately does not reproduce an organization’s actual offboarding policy.

### [local-agent-observability](projects/local-agent-observability/README.md)

This demonstrates local developer/AI tooling in TypeScript: narrow local parsing, privacy/redaction boundaries, source-path protection, session aggregation, durable queues, and local-only processing with no uploader or network dependency.

## Complete project list

| Project | What it demonstrates | Operational posture |
| --- | --- | --- |
| [domain-certificate-observer](projects/domain-certificate-observer/README.md) | A Python monitoring utility for DNS, TLS certificate expiry, optional WHOIS, caching, rate limiting, JSON/CSV output, and monitoring exit codes | **FULL TOOL / READ-ONLY**; live network is opt-in |
| [entra-group-reconciler](projects/entra-group-reconciler/README.md) | PowerShell reconciliation for Entra/Exchange-shaped memberships: complete pagination, identity normalization, guarded diffs, `-WhatIf`, and thresholds | **PROVIDER-READY / MUTATION-CAPABLE**; mock adapter only |
| [entra-reporting-toolbox](projects/entra-reporting-toolbox/README.md) | A reusable PowerShell reporting module for Graph-shaped directory, sign-in, membership, and status data | **PROVIDER-READY / READ-ONLY**; fixture-first |
| [exchange-forwarding-audit](projects/exchange-forwarding-audit/README.md) | A read-only Exchange forwarding investigation pattern with date windows, pagination, retries, current/history correlation, and redacted output | **PROVIDER-READY / READ-ONLY** |
| [idempotent-identity-workflow-engine](projects/idempotent-identity-workflow-engine/README.md) | Phased identity lifecycle orchestration with state, retries, verification, preview, and recovery metadata | **MOCK PROVIDER / MUTATION-CAPABLE**; mock only |
| [identity-address-migration-planner](projects/identity-address-migration-planner/README.md) | Offline UPN/primary-email migration planning with policy, alias preservation, collision detection, and review states | **PLANNING-ONLY** |
| [local-agent-observability](projects/local-agent-observability/README.md) | TypeScript local parsing, privacy redaction, session aggregation, and durable queueing | **FULL TOOL / READ-ONLY / LOCAL-ONLY** |
| [saas-to-itsm-inventory-sync](projects/saas-to-itsm-inventory-sync/README.md) | Provider-neutral Python inventory/ITSM-CMDB matching, payload planning, retries, dry-run, and partial-failure journaling | **PROVIDER-READY / MUTATION-CAPABLE**; mock adapter only |
| [hr-directory-identity-sync](projects/hr-directory-identity-sync/README.md) | Python HR normalization, hybrid AD/Entra matching, policy mappings, collision review, verification, and idempotency | **PROVIDER-READY / MOCK PROVIDERS**; dry-run by default |

## Engineering themes

Across these projects, I tend to:

- Separate discovery, normalization, planning, execution, verification, and reporting.
- Prefer deterministic reconciliation over ad hoc “best-effort” updates.
- Treat incomplete pagination or ambiguous identity data as unsafe for mutation.
- Keep thresholds, dry-run, `-WhatIf`, retries, and explicit mutation gates close to the safety boundary.
- Externalize policy and configuration so provider adapters do not become organization-specific business logic.
- Use synthetic fixtures to exercise collisions, partial failure, privacy boundaries, and idempotency.
- Keep credentials, production identifiers, operational records, and private policy outside public examples.

The portfolio map in [docs/portfolio-map.md](docs/portfolio-map.md) shows how these projects fit together.

## Getting started

Each project has its own README, synthetic example, source, and tests. The cross-project commands and current validation status are in [docs/test-matrix.md](docs/test-matrix.md).

- Python projects use Python 3.10+ and the standard library; set `PYTHONPATH=src` from the project directory.
- PowerShell projects target PowerShell 7+ and use Pester tests.
- `local-agent-observability` uses Node.js 20+ and npm for its TypeScript test/build workflow.
- Fixture commands are offline. Provider-ready projects do not connect anywhere until an engineer supplies and reviews an adapter.

## Safety and publication posture

Read [SECURITY.md](SECURITY.md) and [docs/publication-safety.md](docs/publication-safety.md) before adapting a project. Examples use fictional `.example` or `.invalid` namespaces and synthetic records. No project includes a live credential, tenant, directory, mailbox, HR, SaaS, or ITSM configuration.

This preparation tree intentionally has no license. Ownership, permission to publish, and license selection are manual gates; no legal ownership is asserted here. Private preparation reports remain outside the public export.
