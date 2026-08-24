Set-StrictMode -Version Latest

function Get-OptionalProperty {
    param([object]$Object, [string]$Name)
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -ne $property) { return $property.Value }
    return $null
}

function Get-GroupMembershipReport {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object[]]$Groups, [Parameter(Mandatory)][object[]]$Users)
    $usersById = @{}; foreach ($user in $Users) { if ($user.Id) { $usersById[[string]$user.Id] = $user } }
    foreach ($group in $Groups) {
        foreach ($member in @($group.Members)) {
            $user = $usersById[[string]$member.Id]
            [pscustomobject]@{ GroupId=(Get-OptionalProperty $group 'Id'); GroupName=(Get-OptionalProperty $group 'DisplayName'); UserId=(Get-OptionalProperty $member 'Id'); UserPrincipalName=(Get-OptionalProperty $user 'UserPrincipalName'); AccountEnabled=(Get-OptionalProperty $user 'AccountEnabled') }
        }
    }
}

function Get-UserStatusReport {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object[]]$Users)
    foreach ($user in $Users) {
        $upn = [string](Get-OptionalProperty $user 'UserPrincipalName')
        $accountEnabledValue = Get-OptionalProperty $user 'AccountEnabled'
        $accountStatus = if ($null -eq $accountEnabledValue) { 'Missing' } elseif ([bool]$accountEnabledValue) { 'Enabled' } else { 'Disabled' }
        [pscustomobject]@{ Id=(Get-OptionalProperty $user 'Id'); UserPrincipalName=$upn.ToLowerInvariant(); DisplayName=(Get-OptionalProperty $user 'DisplayName'); AccountEnabled=if ($null -eq $accountEnabledValue) {$null} else {[bool]$accountEnabledValue}; AccountStatus=$accountStatus; CreatedDateTime=(Get-OptionalProperty $user 'CreatedDateTime'); LastSignInDateTime=(Get-OptionalProperty $user 'LastSignInDateTime') }
    }
}

function Get-UserDomainReport {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object[]]$Users)
    $Users | Group-Object { if ([string](Get-OptionalProperty $_ 'UserPrincipalName') -match '@(.+)$') { $Matches[1].ToLowerInvariant() } else { '[invalid]' } } | ForEach-Object {
        [pscustomobject]@{ Domain=$_.Name; UserCount=$_.Count; EnabledCount=@($_.Group | Where-Object AccountEnabled).Count }
    } | Sort-Object Domain
}

function Resolve-EntraObjectId {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object[]]$Objects, [Parameter(Mandatory)][string]$Query)
    $needle = $Query.Trim().ToLowerInvariant()
    $resolved = @($Objects | Where-Object { @((Get-OptionalProperty $_ 'Id'),(Get-OptionalProperty $_ 'DisplayName'),(Get-OptionalProperty $_ 'UserPrincipalName'),(Get-OptionalProperty $_ 'Mail')) | Where-Object { [string]$_ -and ([string]$_).ToLowerInvariant() -eq $needle } } | ForEach-Object { [pscustomobject]@{Id=(Get-OptionalProperty $_ 'Id');DisplayName=(Get-OptionalProperty $_ 'DisplayName');UserPrincipalName=(Get-OptionalProperty $_ 'UserPrincipalName');Mail=(Get-OptionalProperty $_ 'Mail')} })
    if ($resolved.Count -eq 0) { return [pscustomobject]@{Status='NotFound'; Query=$Query; MatchCount=0; Id=$null; DisplayName=$null; UserPrincipalName=$null; Mail=$null; Matches=@()} }
    if ($resolved.Count -gt 1) { return [pscustomobject]@{Status='Ambiguous'; Query=$Query; MatchCount=$resolved.Count; Id=$null; DisplayName=$null; UserPrincipalName=$null; Mail=$null; Matches=$resolved} }
    $match = $resolved[0]
    [pscustomobject]@{Status='Found'; Query=$Query; MatchCount=1; Id=$match.Id; DisplayName=$match.DisplayName; UserPrincipalName=$match.UserPrincipalName; Mail=$match.Mail; Matches=@($match)}
}

function Get-InactiveUserReport {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object[]]$Users, [Parameter(Mandatory)][datetime]$InactiveBefore)
    $cutoff = $InactiveBefore.ToUniversalTime()
    foreach ($user in $Users) {
        $lastValue = Get-OptionalProperty $user 'LastSignInDateTime'
        $last = if ($lastValue) { ([datetime]$lastValue).ToUniversalTime() } else { $null }
        if ($null -eq $last -or $last -lt $cutoff) {
            [pscustomobject]@{ Id=(Get-OptionalProperty $user 'Id'); UserPrincipalName=(Get-OptionalProperty $user 'UserPrincipalName'); LastSignInDateTime=$last; InactiveBefore=$cutoff; Reason=if ($null -eq $last) {'NoSignInRecorded'} else {'BeforeCutoff'} }
        }
    }
}

function Get-EnterpriseAppSignInReport {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object[]]$Applications, [Parameter(Mandatory)][object[]]$SignInEvents)
    $appsById = @{}; foreach ($app in $Applications) { $appsById[[string]$app.AppId] = $app }
    foreach ($event in $SignInEvents | Sort-Object CreatedDateTime) {
        $app = $appsById[[string]$event.AppId]
        [pscustomobject]@{ AppId=(Get-OptionalProperty $event 'AppId'); AppDisplayName=(Get-OptionalProperty $app 'DisplayName'); CreatedDateTime=(Get-OptionalProperty $event 'CreatedDateTime'); UserPrincipalName=(Get-OptionalProperty $event 'UserPrincipalName'); Status=(Get-OptionalProperty $event 'Status'); FailureReason=(Get-OptionalProperty $event 'FailureReason') }
    }
}

function Get-EntraUserStatus { param([Parameter(Mandatory)][object[]]$Users) Get-UserStatusReport -Users $Users }
function Get-EntraGroupMembership { param([Parameter(Mandatory)][object[]]$Groups, [Parameter(Mandatory)][object[]]$Users) Get-GroupMembershipReport -Groups $Groups -Users $Users }
function Get-EntraUserDomain { param([Parameter(Mandatory)][object[]]$Users) Get-UserDomainReport -Users $Users }
function Get-EntraEnterpriseAppSignIn { param([Parameter(Mandatory)][object[]]$Applications, [Parameter(Mandatory)][object[]]$SignInEvents) Get-EnterpriseAppSignInReport -Applications $Applications -SignInEvents $SignInEvents }

function Get-EntraGraphPagedCollection {
    [CmdletBinding()]
    param([Parameter(Mandatory)][scriptblock]$PageProvider, [int]$MaxPages = 100)
    $items = [System.Collections.Generic.List[object]]::new(); $next = $null; $complete = $false; $pageCount = 0
    for ($page = 1; $page -le [Math]::Max(1, $MaxPages); $page++) {
        $pageCount = $page
        $response = & $PageProvider $next
        if ($null -eq $response) { throw "Graph page $page returned no response." }
        foreach ($item in @((Get-OptionalProperty $response 'value'))) { [void]$items.Add($item) }
        $next = Get-OptionalProperty $response '@odata.nextLink'
        if ([string]::IsNullOrWhiteSpace([string]$next)) { $complete = $true; break }
    }
    [pscustomobject]@{ Items=@($items); Complete=$complete; PageCount=$pageCount }
}

function Invoke-EntraGraphReadOnly {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Uri)
    if (-not (Get-Command Invoke-MgGraphRequest -ErrorAction SilentlyContinue)) { throw 'Microsoft.Graph.Authentication is required for live read-only requests.' }
    # Authentication is intentionally not hidden here. The caller should
    # Connect-MgGraph using its approved delegated/certificate/managed identity
    # flow before invoking this read-only request boundary.
    Invoke-MgGraphRequest -Method GET -Uri $Uri -ErrorAction Stop
}

Export-ModuleMember -Function Get-GroupMembershipReport,Get-UserStatusReport,Get-UserDomainReport,Resolve-EntraObjectId,Get-InactiveUserReport,Get-EnterpriseAppSignInReport,Get-EntraUserStatus,Get-EntraGroupMembership,Get-EntraUserDomain,Get-EntraEnterpriseAppSignIn,Get-EntraGraphPagedCollection,Invoke-EntraGraphReadOnly
