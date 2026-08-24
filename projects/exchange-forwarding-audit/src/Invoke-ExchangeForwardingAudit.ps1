[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$CurrentStatePath,
    [Parameter(Mandatory)][string]$AuditEventsPath,
    [datetime]$StartDate = ([datetime]'2030-01-01T00:00:00Z'),
    [datetime]$EndDate = ([datetime]'2030-12-31T23:59:59Z'),
    [ValidateSet('Json','Csv')][string]$OutputFormat = 'Json',
    [string]$OutputPath,
    [string]$ConfigPath,
    [switch]$IncludeForwardingAddresses
)

Import-Module (Join-Path $PSScriptRoot 'ExchangeForwardingAudit.psm1') -Force
$current = @(Get-Content -LiteralPath $CurrentStatePath -Raw | ConvertFrom-Json)
$events = @(Get-Content -LiteralPath $AuditEventsPath -Raw | ConvertFrom-Json)
$config = if ($ConfigPath) { Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json } else { $null }
if ($config) {
    if (-not $PSBoundParameters.ContainsKey('StartDate') -and $config.start_date) { $StartDate = [datetime]$config.start_date }
    if (-not $PSBoundParameters.ContainsKey('EndDate') -and $config.end_date) { $EndDate = [datetime]$config.end_date }
}
$report = @(New-ForwardingAuditReport -CurrentState $current -AuditEvents $events -StartDate $StartDate -EndDate $EndDate -CurrentStateComplete $true -AuditEventsComplete $true)
$report = @(Protect-ForwardingAuditReport -Report $report -IncludeForwardingAddresses:$IncludeForwardingAddresses)
if ($OutputPath) {
    if ($OutputFormat -eq 'Csv') { $report | Export-Csv -LiteralPath $OutputPath -NoTypeInformation }
    else { $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutputPath -Encoding utf8 }
} elseif ($OutputFormat -eq 'Csv') { $report | ConvertTo-Csv -NoTypeInformation } else { $report | ConvertTo-Json -Depth 6 }
