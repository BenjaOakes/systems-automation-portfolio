[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$FixturePath,
    [ValidateSet('GroupMembership','UserStatus','UserDomain','ObjectId','InactiveUser','EnterpriseAppSignIn')][string]$Report = 'UserStatus',
    [string]$Query,
    [datetime]$InactiveBefore = ([datetime]'2030-01-01T00:00:00Z'),
    [string]$OutputPath,
    [ValidateSet('Json','Csv')][string]$OutputFormat = 'Json',
    [string]$ConfigPath
)
Import-Module (Join-Path $PSScriptRoot 'EntraReportingToolbox.psm1') -Force
$config = if ($ConfigPath) { Import-PowerShellDataFile -LiteralPath $ConfigPath } else { $null }
if ($config -and -not $PSBoundParameters.ContainsKey('OutputFormat') -and $config.OutputFormat) { $OutputFormat = [string]$config.OutputFormat }
$data = Get-Content -LiteralPath $FixturePath -Raw | ConvertFrom-Json
$result = switch ($Report) {
    'GroupMembership' { Get-EntraGroupMembership -Groups @($data.groups) -Users @($data.users) }
    'UserStatus' { Get-EntraUserStatus -Users @($data.users) }
    'UserDomain' { Get-EntraUserDomain -Users @($data.users) }
    'ObjectId' { if ([string]::IsNullOrWhiteSpace($Query)) { throw 'Query is required when Report is ObjectId.' }; Resolve-EntraObjectId -Objects @($data.users) -Query $Query }
    'InactiveUser' { Get-InactiveUserReport -Users @($data.users) -InactiveBefore $InactiveBefore }
    'EnterpriseAppSignIn' { Get-EntraEnterpriseAppSignIn -Applications @($data.applications) -SignInEvents @($data.signIns) }
}
$serialized = if ($OutputFormat -eq 'Csv') { @($result) | ConvertTo-Csv -NoTypeInformation } else { @($result) | ConvertTo-Json -Depth 8 }
if ($OutputPath) { $serialized | Set-Content -LiteralPath $OutputPath -Encoding utf8 }
$serialized
