Set-StrictMode -Version Latest

$script:WorkflowSchemaVersion = 1

function Get-WorkflowProperty {
    param([object]$Object, [string]$Name)
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -ne $property) { return $property.Value }
    return $null
}

function New-MockIdentityProvider {
    [CmdletBinding()]
    param([string]$IdentityId = 'fixture-user-001')
    $provider = [pscustomobject]@{
        Identities = @{ $IdentityId = [pscustomobject]@{Id=$IdentityId; Enabled=$true} }
        Groups = @{ $IdentityId = @('fixture-group-001','fixture-group-002') }
        Mailboxes = @{ $IdentityId = [pscustomobject]@{Enabled=$true} }
        Devices = @{ $IdentityId = @([pscustomobject]@{Id='fixture-device-001'; Retired=$false}) }
        Calls = [System.Collections.Generic.List[string]]::new()
    }
    $provider | Add-Member NoteProperty Operations @{
        GetIdentity = { param($id) $provider.Identities[$id] }
        SuspendIdentity = { param($id) $provider.Identities[$id].Enabled=$false; [void]$provider.Calls.Add("SuspendIdentity:$id") }
        GetGroups = { param($id) @($provider.Groups[$id]) }
        RemoveGroup = { param($id,$group) $provider.Groups[$id]=@($provider.Groups[$id] | Where-Object { $_ -ne $group }); [void]$provider.Calls.Add("RemoveGroup:${id}:$group") }
        GetMailbox = { param($id) $provider.Mailboxes[$id] }
        DisableMailbox = { param($id) $provider.Mailboxes[$id].Enabled=$false; [void]$provider.Calls.Add("DisableMailbox:$id") }
        GetDevices = { param($id) @($provider.Devices[$id]) }
        RetireDevice = { param($id,$device) $device.Retired=$true; [void]$provider.Calls.Add("RetireDevice:${id}:$($device.Id)") }
    }
    $provider
}

function New-WorkflowState {
    param([Parameter(Mandatory)][string]$IdentityId)
    [pscustomobject]@{
        SchemaVersion = $script:WorkflowSchemaVersion
        IdentityId = $IdentityId
        Status = 'NotStarted'
        CompletedSteps = @()
        PendingSteps = @()
        Attempts = @{}
        RollbackPlan = @()
        FailedStep = $null
        Error = $null
        UpdatedUtc = [datetime]::UtcNow
    }
}

function Read-WorkflowState {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$IdentityId)
    if (-not (Test-Path -LiteralPath $Path)) { return New-WorkflowState -IdentityId $IdentityId }
    try {
        $parsed = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw "Workflow state could not be read or parsed: $Path"
    }
    $storedIdentity = [string](Get-WorkflowProperty $parsed 'IdentityId')
    if ([string]::IsNullOrWhiteSpace($storedIdentity) -or $storedIdentity -cne $IdentityId) {
        throw "Workflow state identity does not match requested identity: $IdentityId"
    }
    $schemaVersion = Get-WorkflowProperty $parsed 'SchemaVersion'
    if ($null -eq $schemaVersion -or [int]$schemaVersion -ne $script:WorkflowSchemaVersion) {
        throw "Workflow state schema is unsupported or stale for identity: $IdentityId"
    }
    $attempts = @{}
    $attemptProperty = Get-WorkflowProperty $parsed 'Attempts'
    if ($null -ne $attemptProperty) {
        foreach ($property in $attemptProperty.PSObject.Properties) { $attempts[$property.Name] = [int]$property.Value }
    }
    [pscustomobject]@{
        SchemaVersion = $script:WorkflowSchemaVersion
        IdentityId = $storedIdentity
        Status = [string](Get-WorkflowProperty $parsed 'Status')
        CompletedSteps = @((Get-WorkflowProperty $parsed 'CompletedSteps'))
        PendingSteps = @((Get-WorkflowProperty $parsed 'PendingSteps'))
        Attempts = $attempts
        RollbackPlan = @((Get-WorkflowProperty $parsed 'RollbackPlan'))
        FailedStep = Get-WorkflowProperty $parsed 'FailedStep'
        Error = Get-WorkflowProperty $parsed 'Error'
        UpdatedUtc = Get-WorkflowProperty $parsed 'UpdatedUtc'
    }
}

function Write-WorkflowState {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object]$State, [Parameter(Mandatory)][string]$Path)
    $identity = [string](Get-WorkflowProperty $State 'IdentityId')
    if ([string]::IsNullOrWhiteSpace($identity)) { throw 'Workflow state must contain an identity.' }
    $schema = Get-WorkflowProperty $State 'SchemaVersion'
    if ($null -eq $schema -or [int]$schema -ne $script:WorkflowSchemaVersion) { throw 'Workflow state schema is unsupported.' }
    $parent = Split-Path -Parent $Path
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    $State.UpdatedUtc = [datetime]::UtcNow
    $temporaryPath = "$Path.$([guid]::NewGuid().ToString('N')).tmp"
    $json = $State | ConvertTo-Json -Depth 10
    try {
        [System.IO.File]::WriteAllText($temporaryPath, $json, [System.Text.UTF8Encoding]::new($false))
        [System.IO.File]::Move($temporaryPath, $Path, $true)
    } finally {
        if (Test-Path -LiteralPath $temporaryPath) { Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue }
    }
}

function Test-WorkflowTransientError {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object]$ErrorRecord)
    $exception = if ($ErrorRecord -is [System.Management.Automation.ErrorRecord]) { $ErrorRecord.Exception } elseif ($ErrorRecord -is [System.Exception]) { $ErrorRecord } else { $null }
    if ($null -eq $exception) { return $false }
    if ($exception.Data.Contains('Retryable')) { return [bool]$exception.Data['Retryable'] }
    if ($exception.GetType().Name -in @('TimeoutException','IOException','HttpRequestException')) { return $true }
    return ([string]$exception.Message -match '(?i)transient|temporar|timeout|throttl|\b429\b|\b5\d{2}\b')
}

function Invoke-WorkflowOperation {
    [CmdletBinding()]
    param([Parameter(Mandatory)][scriptblock]$Operation, [int]$Attempts = 3)
    $limit = [Math]::Max(1, $Attempts)
    for ($attempt=1; $attempt -le $limit; $attempt++) {
        try {
            & $Operation | Out-Null
            return
        } catch {
            if ($attempt -ge $limit -or -not (Test-WorkflowTransientError $_)) { throw }
            Start-Sleep -Milliseconds (20 * $attempt)
        }
    }
}

function Get-WorkflowRollbackPlan {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object]$State)
    @($State.RollbackPlan)
}

function Invoke-WorkflowStep {
    param([Parameter(Mandatory)][object]$Provider, [Parameter(Mandatory)][string]$IdentityId, [Parameter(Mandatory)][string]$Step)
    switch ($Step) {
        'SuspendIdentity' { & $Provider.Operations.SuspendIdentity $IdentityId | Out-Null }
        'RemoveGroupMemberships' { foreach ($group in @(& $Provider.Operations.GetGroups $IdentityId)) { & $Provider.Operations.RemoveGroup $IdentityId $group | Out-Null } }
        'DisableMailbox' { if ((& $Provider.Operations.GetMailbox $IdentityId).Enabled) { & $Provider.Operations.DisableMailbox $IdentityId | Out-Null } }
        'RetireDevices' { foreach ($device in @(& $Provider.Operations.GetDevices $IdentityId)) { if (-not $device.Retired) { & $Provider.Operations.RetireDevice $IdentityId $device | Out-Null } } }
        default { throw "Unknown workflow step: $Step" }
    }
}

function Test-WorkflowStep {
    param([Parameter(Mandatory)][object]$Provider, [Parameter(Mandatory)][string]$IdentityId, [Parameter(Mandatory)][string]$Step)
    switch ($Step) {
        'SuspendIdentity' { return -not (& $Provider.Operations.GetIdentity $IdentityId).Enabled }
        'RemoveGroupMemberships' { return @(& $Provider.Operations.GetGroups $IdentityId).Count -eq 0 }
        'DisableMailbox' { return -not (& $Provider.Operations.GetMailbox $IdentityId).Enabled }
        'RetireDevices' { return @(& $Provider.Operations.GetDevices $IdentityId | Where-Object { -not $_.Retired }).Count -eq 0 }
        default { throw "Unknown workflow step: $Step" }
    }
}

function Invoke-IdentityWorkflow {
    [CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
    param(
        [Parameter(Mandatory)][object]$Provider,
        [Parameter(Mandatory)][string]$IdentityId,
        [Parameter(Mandatory)][string]$StatePath,
        [switch]$Execute,
        [switch]$WritePreview,
        [string[]]$ProtectedIdentities = @(),
        [int]$MaxAttempts = 3,
        [string[]]$Steps = @('SuspendIdentity','RemoveGroupMemberships','DisableMailbox','RetireDevices')
    )
    if ($IdentityId -in $ProtectedIdentities) { throw "Protected identity cannot be processed: $IdentityId" }
    $identity = & $Provider.Operations.GetIdentity $IdentityId
    if ($null -eq $identity) { throw "Identity not found in provider: $IdentityId" }
    $state = Read-WorkflowState -Path $StatePath -IdentityId $IdentityId
    $steps = @($Steps)
    if ($steps.Count -eq 0) { throw 'At least one workflow step is required.' }
    $completed = [System.Collections.Generic.HashSet[string]]::new()
    $staleCompleted = [System.Collections.Generic.List[string]]::new()
    foreach ($step in @($state.CompletedSteps)) {
        if ($step -notin $steps) { throw "Workflow state contains an unknown completed step: $step" }
        if (Test-WorkflowStep -Provider $Provider -IdentityId $IdentityId -Step $step) { [void]$completed.Add($step) } else { [void]$staleCompleted.Add($step) }
    }
    $pending = @($steps | Where-Object { -not $completed.Contains($_) })
    $rollback = @($steps | ForEach-Object { "Restore$_" })
    if (-not $Execute) {
        $statePersisted = $false
        if ($WritePreview) {
            $state.CompletedSteps = @($completed | Sort-Object)
            $state.PendingSteps = $pending
            $state.Status = 'Preview'
            $state.RollbackPlan = $rollback
            Write-WorkflowState -State $state -Path $StatePath
            $statePersisted = $true
        }
        return [pscustomobject]@{Mode='Preview'; IdentityId=$IdentityId; PendingSteps=$pending; StaleCompletedSteps=@($staleCompleted); StatePath=$StatePath; StatePersisted=$statePersisted; RollbackPlan=$rollback}
    }
    $whatIfOnly = $false
    foreach ($step in $pending) {
        if (-not $PSCmdlet.ShouldProcess($IdentityId, "Run workflow step $step")) { $whatIfOnly = $true; continue }
        try {
            Invoke-WorkflowOperation -Operation { Invoke-WorkflowStep -Provider $Provider -IdentityId $IdentityId -Step $step } -Attempts $MaxAttempts
            if (-not (Test-WorkflowStep -Provider $Provider -IdentityId $IdentityId -Step $step)) { throw "Post-step verification failed: $step" }
            [void]$completed.Add($step)
            $state.CompletedSteps = @($completed | Sort-Object)
            $state.Attempts[$step] = [int]($state.Attempts[$step] ?? 0) + 1
            $state.RollbackPlan = $rollback
            $state.Status = 'InProgress'
            Write-WorkflowState -State $state -Path $StatePath
        } catch {
            $state.Status = 'Failed'
            $state.FailedStep = $step
            $state.Error = $_.Exception.Message
            $state.CompletedSteps = @($completed | Sort-Object)
            Write-WorkflowState -State $state -Path $StatePath
            throw
        }
    }
    if ($whatIfOnly) {
        return [pscustomobject]@{Mode='Execute'; IdentityId=$IdentityId; Status='WhatIf'; PendingSteps=$pending; StatePath=$StatePath; StatePersisted=$false; RollbackPlan=$rollback}
    }
    $state.Status = if ($completed.Count -eq $steps.Count) { 'Completed' } else { 'InProgress' }
    $state.RollbackPlan = $rollback
    Write-WorkflowState -State $state -Path $StatePath
    [pscustomobject]@{Mode='Execute'; IdentityId=$IdentityId; Status=$state.Status; CompletedSteps=@($completed | Sort-Object); StatePath=$StatePath; StatePersisted=$true; RollbackPlan=@($state.RollbackPlan)}
}

Export-ModuleMember -Function New-MockIdentityProvider,Read-WorkflowState,Write-WorkflowState,Test-WorkflowTransientError,Invoke-WorkflowOperation,Get-WorkflowRollbackPlan,Invoke-IdentityWorkflow
