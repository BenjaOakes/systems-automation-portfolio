# Test matrix

This matrix is for the nine public projects. Commands are run from the named project directory and use only synthetic fixtures unless explicitly marked otherwise.

## Common commands

Python projects:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
```

PowerShell projects:

```powershell
$config = New-PesterConfiguration
$config.Run.Path = @(".\tests")
$config.Run.Exit = $true
$config.TestDrive.Enabled = $false
$config.TestRegistry.Enabled = $false
Invoke-Pester -Configuration $config
```

The suites use workspace-local temporary state where needed. Disabling the Pester TestDrive/TestRegistry plugins makes the command reproducible in restricted environments where registry-backed Pester setup is unavailable; it does not disable the project’s own tests.

## Project matrix

| Project | Language | Test command | Fixture/example command | Dependencies | Live provider / operation | Validation status |
| --- | --- | --- | --- | --- | --- | --- |
| domain-certificate-observer | Python | Common Python command | `python -m domain_observer.cli --fixture examples/domains.fixture.json --json` | Python 3.10+, standard library | No live provider required for fixture; live DNS/TLS/WHOIS is opt-in and read-only | PASS; fixture intentionally exits 1 for an expired synthetic certificate |
| entra-group-reconciler | PowerShell | Common Pester command | `& .\src\Invoke-GroupReconciliation.ps1 -FixturePath .\examples\membership.fixture.json` and add `-Execute` for mock mutation | PowerShell 7+, Pester 5+ | No live adapter included; a future Graph/Exchange adapter would be mutation-capable behind explicit gates | PASS |
| entra-reporting-toolbox | PowerShell | Common Pester command | `& .\src\Invoke-EntraReport.ps1 -FixturePath .\examples\directory.fixture.json -Report GroupMembership` | PowerShell 7+, Pester 5+ | Fixture/read-only; caller-supplied Graph authentication and GET boundary only | PASS |
| exchange-forwarding-audit | PowerShell | Common Pester command | `& .\src\Invoke-ExchangeForwardingAudit.ps1 -CurrentStatePath .\examples\current-state.fixture.json -AuditEventsPath .\examples\audit-events.fixture.json -OutputFormat Json` | PowerShell 7+, Pester 5+ | Fixture/read-only; a separate administrator-reviewed Graph/Exchange query adapter is required | PASS |
| idempotent-identity-workflow-engine | PowerShell | Common Pester command | `& .\src\Invoke-DemoWorkflow.ps1 -Execute -WhatIf`; mock execution may use `-Execute -StatePath .\output\fixture-state.json` | PowerShell 7+, Pester 5+ | Mock mutation only; no live offboarding provider | PASS |
| identity-address-migration-planner | Python | Common Python command | `python -m identity_planner.cli --input examples/users.fixture.json --policy examples/policy.json --json` | Python 3.10+, standard library | Planning-only; no provider or mutation | PASS |
| local-agent-observability | TypeScript | `npm ci; npm test; npm run build` | `npm run dev -- --input examples/session.fixture.jsonl --output .\output\local-report.json` | Node.js 20+, npm, locked dev dependencies | Local-only; no network or uploader | PASS |
| saas-to-itsm-inventory-sync | Python | Common Python command | `python -m itsm_sync.cli --fixture examples/inventory.fixture.json --json` and add `--execute` for mock mutation | Python 3.10+, standard library | No vendor adapter; caller-supplied source/target adapters are mutation-capable | PASS |
| hr-directory-identity-sync | Python | Common Python command | `python -m hr_directory_sync.cli --employees examples/employees.example.csv --directory examples/directory.example.json --policy config/identity-policy.example.json` | Python 3.10+, standard library | Mock HR/Entra/AD providers only; real adapters require separate permissions and review | PASS; fixture intentionally exits 1 for blocked/review rows |

## Additional validation

- PowerShell syntax: parse every `.ps1`, `.psm1`, and `.psd1` file with `[System.Management.Automation.Language.Parser]::ParseFile`.
- Python syntax: compile every `.py` file with `python -m compileall -q` or rely on the unit-test imports.
- JSON/JSONL: validate `.json` with a JSON parser and parse each line of `.jsonl` independently.
- TOML: parse every `.toml` with Python’s `tomllib`.
- YAML: the committed YAML files are configuration templates; the runnable CLIs intentionally use JSON and the templates receive manual structural review unless an approved YAML parser is available.
- Never run live-provider commands or real mutation commands as part of this matrix.

