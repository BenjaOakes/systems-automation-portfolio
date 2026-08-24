Set-StrictMode -Version Latest

function Get-AuditProperty {
    param([object]$Object, [string]$Name)
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -ne $property) { return $property.Value }
    return $null
}

function Test-AuditDateWindow {
    [CmdletBinding()]
    param([datetime]$StartDate, [datetime]$EndDate)
    if ($EndDate -le $StartDate) { throw 'EndDate must be later than StartDate.' }
    [pscustomobject]@{ StartDate = $StartDate.ToUniversalTime(); EndDate = $EndDate.ToUniversalTime() }
}

function Test-AuditRetryableError {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object]$ErrorRecord)
    $exception = if ($ErrorRecord -is [System.Management.Automation.ErrorRecord]) { $ErrorRecord.Exception } elseif ($ErrorRecord -is [System.Exception]) { $ErrorRecord } else { $null }
    if ($null -eq $exception) { return $false }
    if ($exception.Data.Contains('Retryable')) { return [bool]$exception.Data['Retryable'] }
    if ($exception.GetType().Name -in @('TimeoutException','IOException','HttpRequestException')) { return $true }
    return ([string]$exception.Message -match '(?i)transient|temporar|timeout|throttl|\b429\b|\b5\d{2}\b')
}

function Invoke-AuditRetry {
    [CmdletBinding()]
    param([Parameter(Mandatory)][scriptblock]$Operation, [int]$Attempts = 3, [int]$BaseDelayMilliseconds = 25, [scriptblock]$RetryWhen)
    $lastError = $null
    $limit = [Math]::Max(1, $Attempts)
    for ($attempt = 1; $attempt -le $limit; $attempt++) {
        try { return & $Operation }
        catch {
            $lastError = $_
            $retryable = if ($RetryWhen) { [bool](& $RetryWhen $_) } else { Test-AuditRetryableError $_ }
            if ($attempt -ge $limit -or -not $retryable) { break }
            Start-Sleep -Milliseconds ($BaseDelayMilliseconds * [Math]::Pow(2, $attempt - 1))
        }
    }
    throw $lastError
}

function Get-PagedRecords {
    [CmdletBinding()]
    param([Parameter(Mandatory)][scriptblock]$PageProvider, [int]$MaxPages = 100)
    $items = [System.Collections.Generic.List[object]]::new()
    $next = $null
    $complete = $false
    $pageCount = 0
    for ($page = 1; $page -le [Math]::Max(1, $MaxPages); $page++) {
        $pageCount = $page
        $response = Invoke-AuditRetry -Operation { & $PageProvider $next }
        if ($null -eq $response) { throw "Page $page returned no response." }
        foreach ($item in @($response.Items)) { [void]$items.Add($item) }
        $next = $response.NextLink
        if ([string]::IsNullOrWhiteSpace([string]$next)) { $complete = ($response.Complete -ne $false); break }
    }
    [pscustomobject]@{ Items = @($items); Complete = $complete; PageCount = $pageCount }
}

function New-ForwardingAuditReport {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][AllowEmptyCollection()][object[]]$CurrentState,
        [Parameter(Mandatory)][AllowEmptyCollection()][object[]]$AuditEvents,
        [Parameter(Mandatory)][datetime]$StartDate,
        [Parameter(Mandatory)][datetime]$EndDate,
        [bool]$CurrentStateComplete = $true,
        [bool]$AuditEventsComplete = $true
    )
    $window = Test-AuditDateWindow -StartDate $StartDate -EndDate $EndDate
    if (-not $CurrentStateComplete -or -not $AuditEventsComplete) { throw 'Current state and audit collections must be complete before correlation.' }
    $currentByUser = @{}
    foreach ($state in $CurrentState) {
        $key = ([string]$state.UserPrincipalName).Trim().ToLowerInvariant()
        if ($key) {
            if ($currentByUser.ContainsKey($key)) { throw "Duplicate current forwarding state for: $key" }
            $currentByUser[$key] = $state
        }
    }
    $eventsByUser = @{}
    foreach ($event in $AuditEvents) {
        $time = [datetime]$event.Timestamp
        if ($time.ToUniversalTime() -lt $window.StartDate -or $time.ToUniversalTime() -gt $window.EndDate) { continue }
        $key = ([string]$event.UserPrincipalName).Trim().ToLowerInvariant()
        if (-not $eventsByUser.ContainsKey($key)) { $eventsByUser[$key] = [System.Collections.Generic.List[object]]::new() }
        [void]$eventsByUser[$key].Add($event)
    }
    $users = @($currentByUser.Keys + $eventsByUser.Keys | Sort-Object -Unique)
    foreach ($user in $users) {
        $state = $currentByUser[$user]
        $history = if ($eventsByUser.ContainsKey($user)) { @($eventsByUser[$user] | ForEach-Object { $_ } | Sort-Object Timestamp) } else { @() }
        $historyCount = @($history).Count
        $currentEnabled = if ($null -ne $state) { [bool](Get-AuditProperty $state 'ForwardingEnabled') } else { $null }
        $correlation = if ($null -ne $state -and $historyCount) { 'CurrentAndHistorical' } elseif ($null -ne $state) { 'CurrentOnly' } else { 'HistoricalOnly' }
        [pscustomobject]@{
            UserPrincipalName = $user
            CurrentForwardingEnabled = $currentEnabled
            CurrentForwardingAddress = if ($state) { Get-AuditProperty $state 'ForwardingAddress' } else { $null }
            CurrentDeliverToMailboxAndForward = if ($state) { Get-AuditProperty $state 'DeliverToMailboxAndForward' } else { $null }
            HistoricalEventCount = $historyCount
            FirstHistoricalEvent = if ($historyCount) { @($history)[0].Timestamp } else { $null }
            LastHistoricalEvent = if ($historyCount) { @($history)[-1].Timestamp } else { $null }
            HistoricalOperations = @($history | ForEach-Object { $_.Operation } | Sort-Object -Unique)
            Correlation = $correlation
            WindowStartUtc = $window.StartDate
            WindowEndUtc = $window.EndDate
        }
    }
}

function Protect-ForwardingAuditReport {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object[]]$Report, [switch]$IncludeForwardingAddresses)
    foreach ($row in @($Report)) {
        if (-not $IncludeForwardingAddresses) {
            $row.CurrentForwardingAddress = if ($row.CurrentForwardingAddress) { '[REDACTED_FORWARDING_ADDRESS]' } else { $null }
        }
        $row
    }
}

Export-ModuleMember -Function Test-AuditDateWindow,Test-AuditRetryableError,Invoke-AuditRetry,Get-PagedRecords,New-ForwardingAuditReport,Protect-ForwardingAuditReport
