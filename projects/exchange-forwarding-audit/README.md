# Exchange Forwarding Audit

Operational posture: `PROVIDER-READY / READ-ONLY`. Synthetic fixtures are the default and no cmdlet changes mailbox configuration.

## Problem and use case

Mailbox-forwarding investigations need two views: what is configured now and what audit systems recorded during a time window. Either view alone can mislead after a setting is removed or audit retention expires.

The intended audience is messaging administrators, security operations engineers, incident responders, and PowerShell developers building an investigation report.

## Architecture

`Get-PagedRecords` accepts a page provider that returns `Items`, `NextLink`, and `Complete`. `New-ForwardingAuditReport` validates a UTC date window, requires complete current/history collections, correlates by normalized UPN, and returns current-only, historical-only, or combined rows. `Invoke-AuditRetry` retries only classified transient/throttling/network failures. `Protect-ForwardingAuditReport` redacts forwarding destinations unless the caller explicitly opts into restricted output.

## Installation, configuration, and usage

PowerShell 7+ is recommended. `config/config.example.json` shows fictional `start_date` and `end_date` values; it contains no tenant, app, mailbox, or token settings.

```powershell
Import-Module .\src\ExchangeForwardingAudit.psm1 -Force
& .\src\Invoke-ExchangeForwardingAudit.ps1 -CurrentStatePath .\examples\current-state.fixture.json -AuditEventsPath .\examples\audit-events.fixture.json -OutputFormat Json
& .\src\Invoke-ExchangeForwardingAudit.ps1 -CurrentStatePath .\examples\current-state.fixture.json -AuditEventsPath .\examples\audit-events.fixture.json -OutputFormat Csv -OutputPath .\output\forwarding.csv
```

JSON and CSV are mutually exclusive output contracts: stdout or `-OutputPath` contains only the selected serialization. Forwarding addresses are redacted by default; `-IncludeForwardingAddresses` is an explicit sensitive-report opt-in.

## Connecting a real environment

The included implementation does not contain a live Graph/Exchange query adapter. To adapt it, implement two read-only paged providers: one for current mailbox forwarding state and one for audit events. Each provider must page to completion, return normalized records, classify retryable errors, and preserve the audit retention/date-window boundary. An administrator must choose the minimum read-only mailbox/audit permissions and authentication method for their tenant, then independently review logging and retention before supplying the adapter. See [docs/permissions.md](docs/permissions.md) and [docs/investigation.md](docs/investigation.md).

## Safety, testing, and limitations

The project never calls mailbox mutation cmdlets. It cannot prove that forwarding was malicious and cannot recover events outside provider retention. Pester tests cover date validation, pagination, correlation, retries, and redaction using synthetic data. Treat destination addresses and audit rows as sensitive even when a report is structurally safe.
