[CmdletBinding(SupportsShouldProcess=$true)]
param(
    [Parameter(Mandatory)][string]$FixturePath,
    [string]$ConfigPath = (Join-Path $PSScriptRoot '..\config\config.example.json'),
    [switch]$Execute,
    [int]$MaxChanges = 20,
    [ValidateSet('Json','Csv')][string]$OutputFormat = 'Json',
    [string]$OutputPath
)
Import-Module (Join-Path $PSScriptRoot 'EntraGroupReconciler.psm1') -Force
$fixture = Get-Content -LiteralPath $FixturePath -Raw | ConvertFrom-Json
$config = if (Test-Path -LiteralPath $ConfigPath) { Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json } else { [pscustomobject]@{ page_size = 2; max_changes = $MaxChanges } }
$limit = if ($PSBoundParameters.ContainsKey('MaxChanges')) { $MaxChanges } else { [int]($config.max_changes ?? 20) }
$pageSize = [int]($config.page_size ?? 2)
$sourceProvider = New-MockMembershipProvider -Members @($fixture.source) -PageSize $pageSize
$targetProvider = New-MockMembershipProvider -Members @($fixture.target) -PageSize $pageSize
$sourceCollection = Get-ProviderMembership -Provider $sourceProvider -Operation GetPage
$targetCollection = Get-ProviderMembership -Provider $targetProvider -Operation GetPage
$result = Invoke-MembershipReconciliation -Source @($sourceCollection.Items) -Target @($targetCollection.Items) -SourceComplete ([bool]$fixture.sourceComplete -and $sourceCollection.Complete) -TargetComplete ([bool]$fixture.targetComplete -and $targetCollection.Complete) -Execute:$Execute -WhatIf:$WhatIfPreference -Confirm:$false -MaxChanges $limit -AddMember { param($member) & $targetProvider.Operations.Add $member } -RemoveMember { param($member) & $targetProvider.Operations.Remove $member }
$output = [pscustomobject]@{ Result = $result; ProviderCalls = @($targetProvider.Calls); Mode = if ($Execute) { 'ExecuteMock' } else { 'Preview' } }
$serialized = if ($OutputFormat -eq 'Csv') { $result.Changes | ConvertTo-Csv -NoTypeInformation } else { $output | ConvertTo-Json -Depth 8 }
if ($OutputPath) { $serialized | Set-Content -LiteralPath $OutputPath -Encoding utf8 } else { $serialized }
