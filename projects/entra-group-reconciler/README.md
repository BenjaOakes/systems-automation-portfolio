# Entra Group Reconciler

Operational posture: `PROVIDER-READY / MUTATION-CAPABLE`. The core is reusable and the included adapter is an in-memory mock; preview is the default and no live Graph or Exchange connector is included.

## Problem and use case

Membership synchronization is a set problem with operational consequences. A safe reconciler must collect every page, normalize identities represented differently by two systems, calculate an explainable diff, and refuse to mutate when collection is incomplete, ambiguous, or too large.

The intended audience is identity engineers, messaging/platform engineers, PowerShell developers, and reviewers of guarded automation.

## Architecture

Collection returns items plus a completeness flag. The diff stage is provider-neutral: it builds separate provider-ID and SMTP indexes, correlates unambiguous identities, and rejects duplicates or conflicting evidence. The execution stage receives add/remove scriptblocks and calls them only when `-Execute`, `-WhatIf`, and `ShouldProcess` all permit it. A maximum total-change threshold is enforced before execution.

## Installation and configuration

PowerShell 7+ is recommended. `config/config.example.json` contains only fictional settings for `page_size` and `max_changes`; tenant IDs, group IDs, addresses, certificates, and authentication material do not belong there.

```powershell
Import-Module .\src\EntraGroupReconciler.psm1 -Force
& .\src\Invoke-GroupReconciliation.ps1 -FixturePath .\examples\membership.fixture.json
& .\src\Invoke-GroupReconciliation.ps1 -FixturePath .\examples\membership.fixture.json -Execute
```

The second command mutates only the in-memory mock provider. Add `-OutputFormat Csv` or `-OutputPath .\output\preview.json` for a reviewable artifact; keep generated output under an ignored directory.

## Example and provider contract

The fixture exercises pagination, an SMTP-only target representation, and a real add/remove diff. A provider adapter must expose:

1. A paged collection operation accepting a continuation token and returning `Items`, `NextLink`, and a truthful `Complete` flag.
2. Add and remove operations receiving the normalized member selected by the plan.
3. Authentication, retry/throttling classification, and provider-specific verification outside this module.

For a Microsoft Graph/Exchange adapter, collect the complete source and target membership sets with least-privilege read access, then request only the narrowly scoped target membership write permission needed for the approved group. An engineer must decide whether provider IDs, UPNs, mail, or proxy addresses are authoritative in their environment and preserve the conflict checks. See [docs/provider-development.md](docs/provider-development.md).

## Permissions and safety

Fixture mode needs no cloud permissions. Incomplete pages, duplicate normalized identities, ambiguous correlation, and changes above `max_changes` are blockers. `-Execute` without both mutation adapters fails clearly. The included `-Execute` path is a mock demonstration, not a live provider.

## Testing and limitations

Pester tests cover normalization, pagination, correlation, completeness, thresholds, and `-WhatIf` behavior with synthetic records. This is a reconciliation engine, not a Microsoft Graph or Exchange SDK wrapper; it does not select a tenant, authenticate, retrieve live data, or implement provider-specific rollback.
