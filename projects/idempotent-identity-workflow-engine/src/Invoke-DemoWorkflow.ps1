[CmdletBinding(SupportsShouldProcess=$true)]
param(
    [switch]$Execute,
    [switch]$WritePreview,
    [string]$StatePath = (Join-Path $PSScriptRoot '..\.state\fixture-user-001.json'),
    [string]$ConfigPath = (Join-Path $PSScriptRoot '..\config\config.example.json')
)
Import-Module (Join-Path $PSScriptRoot 'IdentityWorkflowEngine.psm1') -Force
$provider = New-MockIdentityProvider
$config = if (Test-Path -LiteralPath $ConfigPath) { Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json } else { [pscustomobject]@{ identity_id='fixture-user-001'; protected_identities=@('fixture-break-glass'); max_attempts=3 } }
$identityId = [string]($config.identity_id ?? 'fixture-user-001')
$protected = @($config.protected_identities)
$attempts = [int]($config.max_attempts ?? 3)
$steps = @($config.phases)
if ($steps.Count -eq 0) { $steps = @('SuspendIdentity','RemoveGroupMemberships','DisableMailbox','RetireDevices') }
$result = Invoke-IdentityWorkflow -Provider $provider -IdentityId $identityId -StatePath $StatePath -Execute:$Execute -WritePreview:$WritePreview -ProtectedIdentities $protected -MaxAttempts $attempts -Steps $steps -WhatIf:$WhatIfPreference -Confirm:$false
$result | ConvertTo-Json -Depth 8
