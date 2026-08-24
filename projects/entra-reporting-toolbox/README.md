# Entra Reporting Toolbox

Operational posture: `PROVIDER-READY / READ-ONLY`. The reporting transformations are reusable and fixture-first; no live provider is connected by default.

## Problem and use case

Directory reporting jobs often become a collection of one-off scripts. Pagination, normalization, related-object joins, date filtering, ambiguity handling, and stable output are better kept in a coherent read-only toolbox.

The intended audience is identity administrators, security analysts, reporting engineers, and PowerShell developers who need repeatable Entra-shaped reports.

## Architecture

`EntraReportingToolbox.psm1` contains pure transformations over supplied Graph-shaped objects: group membership, user status, user-domain summaries, object-ID resolution, inactivity, and enterprise-application sign-in reports. `Get-EntraGraphPagedCollection` handles a Graph-style `value` / `@odata.nextLink` boundary, while `Invoke-EntraGraphReadOnly` is a small GET-only request boundary. Authentication remains the caller’s responsibility.

## Installation, configuration, and fixture usage

PowerShell 7+ is recommended. `config/config.example.psd1` shows non-secret output settings and fictional placeholders. It contains no tenant, application, group, or token value.

```powershell
Import-Module .\src\EntraReportingToolbox.psm1 -Force
& .\src\Invoke-EntraReport.ps1 -FixturePath .\examples\directory.fixture.json -Report GroupMembership
& .\src\Invoke-EntraReport.ps1 -FixturePath .\examples\directory.fixture.json -Report UserStatus -OutputFormat Csv
& .\src\Invoke-EntraReport.ps1 -FixturePath .\examples\directory.fixture.json -Report ObjectId -Query user.one@brand-a.example
```

The report names are `GroupMembership`, `UserStatus`, `UserDomain`, `ObjectId`, `InactiveUser`, and `EnterpriseAppSignIn`. JSON is the default; `-OutputPath` writes a local report. Fixture mode never authenticates or calls a service.

## Connecting a real environment

An operator can authenticate with an approved Microsoft Graph flow before calling the read-only boundary, for example a delegated, certificate-based, or managed-identity flow handled by their environment. The required permissions depend on the report and should be least-privilege read/report permissions; sign-in reports may require audit-log permissions and retention access. Never log tokens or raw report rows.

The adapter must page every collection, map the response into the fixture-shaped objects, preserve missing-vs-disabled fields, and surface ambiguous object-ID matches instead of guessing. The module performs no mutation and has no tenant-specific defaults. See [docs/authentication.md](docs/authentication.md).

## Output, safety, testing, and limitations

Reports return structured PowerShell objects that can be piped to `ConvertTo-Json`, `ConvertTo-Csv`, or another approved sink. Missing `AccountEnabled` is reported as `Missing`, not as disabled; object-ID lookup returns `Found`, `NotFound`, or `Ambiguous`. Pester tests validate every report component with synthetic directory objects. The project does not authenticate, retrieve live Graph data, or mutate directory state.
