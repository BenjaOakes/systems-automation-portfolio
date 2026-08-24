# Idempotent Identity Workflow Engine

Operational posture: `MOCK PROVIDER / MUTATION-CAPABLE`. The included execute path mutates only a local mock provider; preview and `-WhatIf` are safe defaults.

## Problem and use case

High-risk identity work is a sequence, not a single API call. It needs phases, durable identity-bound state, retries, post-step verification, protected-object checks, preview behavior, and a recovery story when a later step fails.

This workflow pattern is based on engineering patterns I have used for high-risk identity lifecycle workflows such as employee offboarding. The public implementation demonstrates the safety mechanics without reproducing an organization’s actual offboarding policy or production actions.

### Example use case: employee offboarding

An employee offboarding system may need to coordinate identity state, sessions, authentication methods, devices, mailboxes, group membership, verification, and rollback/recovery planning. This project demonstrates the engineering pattern for such a workflow; it does not publish an organization’s offboarding policy, access rules, or production actions.

The intended audience is systems engineers, identity automation developers, platform engineers, and reviewers designing safe long-running workflows.

## Architecture

The engine owns sequencing, stable step names, state schema, retries, and verification. The provider owns resource reads and operations. State is identity-validated and atomically replaced after successful phases; preview does not persist state unless `-WritePreview` is explicit. A rollback plan is metadata only because automatic reversal can be dangerous.

## Installation, configuration, and usage

PowerShell 7+ is recommended. `config/config.example.json` controls the synthetic identity, protected identities, phases, and retry limit.

```powershell
& .\src\Invoke-DemoWorkflow.ps1
& .\src\Invoke-DemoWorkflow.ps1 -Execute -WhatIf
& .\src\Invoke-DemoWorkflow.ps1 -Execute -StatePath .\output\fixture-state.json
& .\src\Invoke-DemoWorkflow.ps1 -WritePreview -StatePath .\output\preview.json
```

The first two commands do not persist state. The third mutates only the in-memory mock and writes local state under an ignored path. The fourth intentionally records a preview.

## Provider development

A real adapter would implement identity lookup, identity suspension, group enumeration/removal, mailbox lookup/disable, device enumeration/retirement, and post-step reads used by verification. Authentication, authorization, retries, idempotency keys, provider-specific rollback, backup/restore, and change approval must remain adapter/operations concerns. No Microsoft 365 or other live provider is included.

## Safety, testing, and limitations

Protected identities are refused, `-Execute` is required for mutation, `-WhatIf` leaves persistent state untouched, and a failed step is recorded before the error is surfaced. Pester tests cover protected users, state identity/schema, preview, `-WhatIf`, retries, verification, and resume. The mock provider is not a Microsoft 365 emulator; rollback is deliberately not automatic.
