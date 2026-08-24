Set-StrictMode -Version Latest

function Get-OptionalMemberProperty {
    param([object]$Object, [string]$Name)
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -ne $property) { return $property.Value }
    return $null
}

function ConvertTo-NormalizedIdentity {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object]$Member)
    $providerId = [string](Get-OptionalMemberProperty $Member 'Id')
    $providerId = $providerId.Trim().ToLowerInvariant()
    $addressKeys = [System.Collections.Generic.List[string]]::new()
    foreach ($value in @(
        (Get-OptionalMemberProperty $Member 'UserPrincipalName'),
        (Get-OptionalMemberProperty $Member 'Mail'),
        (Get-OptionalMemberProperty $Member 'PrimarySmtpAddress')
    )) {
        if (-not [string]::IsNullOrWhiteSpace([string]$value)) {
            $key = "smtp:$(([string]$value).Trim().ToLowerInvariant())"
            if (-not $addressKeys.Contains($key)) { [void]$addressKeys.Add($key) }
        }
    }
    foreach ($proxy in @(Get-OptionalMemberProperty $Member 'ProxyAddresses')) {
        if ([string]::IsNullOrWhiteSpace([string]$proxy)) { continue }
        $address = ([string]$proxy -replace '^(?i:smtp):','').Trim().ToLowerInvariant()
        if ($address) {
            $key = "smtp:$address"
            if (-not $addressKeys.Contains($key)) { [void]$addressKeys.Add($key) }
        }
    }
    if (-not $providerId -and $addressKeys.Count -eq 0) { throw 'Member has no usable provider or SMTP identity.' }
    $correlationKeys = [System.Collections.Generic.List[string]]::new()
    if ($providerId) { [void]$correlationKeys.Add("provider:$providerId") }
    foreach ($key in $addressKeys) { [void]$correlationKeys.Add($key) }
    [pscustomobject]@{
        Key = if ($providerId) { "provider:$providerId" } else { $addressKeys[0] }
        ProviderId = if ($providerId) { $providerId } else { $null }
        AddressKeys = @($addressKeys)
        CorrelationKeys = @($correlationKeys)
        UserPrincipalName = Get-OptionalMemberProperty $Member 'UserPrincipalName'
        Mail = Get-OptionalMemberProperty $Member 'Mail'
        Raw = $Member
    }
}

function Get-GraphPagedCollection {
    [CmdletBinding()]
    param([Parameter(Mandatory)][scriptblock]$PageProvider, [int]$MaxPages = 100)
    $items = [System.Collections.Generic.List[object]]::new(); $next = $null; $complete = $false; $page = 0
    while ($page -lt [Math]::Max(1, $MaxPages)) {
        $page++
        $response = & $PageProvider $next
        if ($null -eq $response) { throw "Page $page returned no response." }
        foreach ($item in @($response.Items)) { [void]$items.Add($item) }
        $next = $response.NextLink
        if ([string]::IsNullOrWhiteSpace([string]$next)) { $complete = ($response.Complete -ne $false); break }
    }
    [pscustomobject]@{ Items = @($items); Complete = $complete; PageCount = $page }
}

function Get-ProviderMembership {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object]$Provider, [Parameter(Mandatory)][string]$Operation, [int]$MaxPages = 100)
    if ($null -eq $Provider.Operations -or $null -eq $Provider.Operations[$Operation]) {
        throw "Provider does not implement the paged operation: $Operation"
    }
    # A continuation boundary is part of the contract. The reconciler must
    # know that every page was collected before it can calculate a diff.
    Get-GraphPagedCollection -PageProvider { param($next) & $Provider.Operations[$Operation] $next } -MaxPages $MaxPages
}

function New-MockMembershipProvider {
    [CmdletBinding()]
    param([Parameter(Mandatory)][AllowEmptyCollection()][object[]]$Members, [int]$PageSize = 2)
    if ($PageSize -lt 1) { throw 'PageSize must be positive.' }
    $provider = [pscustomobject]@{
        Members = [System.Collections.ArrayList]::new()
        Calls = [System.Collections.Generic.List[string]]::new()
        PageSize = $PageSize
        Operations = $null
    }
    foreach ($member in @($Members)) { [void]$provider.Members.Add($member) }
    $getPage = {
            param($next)
            $offset = if ([string]::IsNullOrWhiteSpace([string]$next)) { 0 } else { [int]$next * $provider.PageSize }
            $items = @($provider.Members | Select-Object -Skip $offset -First $provider.PageSize)
            $hasMore = ($offset + $items.Count) -lt $provider.Members.Count
            [void]$provider.Calls.Add("GetPage:$offset")
            [pscustomobject]@{ Items = $items; NextLink = if ($hasMore) { [string]([int]($offset / $provider.PageSize) + 1) } else { $null }; Complete = $true }
        }.GetNewClosure()
    $add = {
            param($member)
            [void]$provider.Members.Add($member.Raw)
            [void]$provider.Calls.Add("Add:$($member.Key)")
        }.GetNewClosure()
    $remove = {
            param($member)
            $key = $member.Key
            foreach ($match in @($provider.Members | Where-Object { (ConvertTo-NormalizedIdentity $_).Key -eq $key })) { [void]$provider.Members.Remove($match) }
            [void]$provider.Calls.Add("Remove:$key")
        }.GetNewClosure()
    $provider.Operations = @{ GetPage = $getPage; Add = $add; Remove = $remove }
    $provider
}

function New-IdentityIndex {
    param([Parameter(Mandatory)][AllowEmptyCollection()][object[]]$Members, [Parameter(Mandatory)][string]$CollectionName)
    $entries = [System.Collections.Generic.List[object]]::new()
    $keyOwners = @{}
    $providerMap = @{}
    $addressMap = @{}
    $index = 0
    foreach ($member in @($Members)) {
        $normalized = ConvertTo-NormalizedIdentity $member
        $normalized | Add-Member NoteProperty IdentityIndex $index
        foreach ($key in @($normalized.CorrelationKeys)) {
            if ($keyOwners.ContainsKey($key)) { throw "Duplicate normalized identity in $CollectionName collection: $key" }
            $keyOwners.Add($key, $normalized)
        }
        if ($normalized.ProviderId) { $providerMap.Add($normalized.ProviderId, $normalized) }
        foreach ($addressKey in @($normalized.AddressKeys)) { $addressMap.Add($addressKey, $normalized) }
        [void]$entries.Add($normalized)
        $index++
    }
    [pscustomobject]@{ Entries=@($entries); ProviderMap=$providerMap; AddressMap=$addressMap }
}

function Get-MembershipDiff {
    [CmdletBinding()]
    param([Parameter(Mandatory)][AllowEmptyCollection()][object[]]$Source, [Parameter(Mandatory)][AllowEmptyCollection()][object[]]$Target, [bool]$SourceComplete = $true, [bool]$TargetComplete = $true)
    if (-not $SourceComplete -or -not $TargetComplete) { throw 'Collection incomplete; refusing to calculate a mutation diff.' }
    $sourceIndex = New-IdentityIndex -Members $Source -CollectionName 'source'
    $targetIndex = New-IdentityIndex -Members $Target -CollectionName 'target'
    $matchedSource = @{}
    $matchedTarget = @{}
    foreach ($sourceMember in @($sourceIndex.Entries)) {
        $candidates = @{}
        if ($sourceMember.ProviderId -and $targetIndex.ProviderMap.ContainsKey($sourceMember.ProviderId)) {
            $candidate = $targetIndex.ProviderMap[$sourceMember.ProviderId]
            $candidates[[string]$candidate.IdentityIndex] = $candidate
        }
        foreach ($addressKey in @($sourceMember.AddressKeys)) {
            if ($targetIndex.AddressMap.ContainsKey($addressKey)) {
                $candidate = $targetIndex.AddressMap[$addressKey]
                $candidates[[string]$candidate.IdentityIndex] = $candidate
            }
        }
        if ($candidates.Count -gt 1) { throw "Ambiguous identity correlation for source member $($sourceMember.Key)." }
        if ($candidates.Count -eq 1) {
            $targetMember = @($candidates.Values)[0]
            if ($sourceMember.ProviderId -and $targetMember.ProviderId -and $sourceMember.ProviderId -cne $targetMember.ProviderId) {
                throw "Ambiguous identity correlation: provider identity conflicts with SMTP identity for $($sourceMember.Key)."
            }
            $matchedSource[[string]$sourceMember.IdentityIndex] = $true
            $matchedTarget[[string]$targetMember.IdentityIndex] = $true
        }
    }
    [pscustomobject]@{
        ToAdd = @($sourceIndex.Entries | Where-Object { -not $matchedSource.ContainsKey([string]$_.IdentityIndex) } | Sort-Object Key)
        ToRemove = @($targetIndex.Entries | Where-Object { -not $matchedTarget.ContainsKey([string]$_.IdentityIndex) } | Sort-Object Key)
        SourceCount = @($sourceIndex.Entries).Count
        TargetCount = @($targetIndex.Entries).Count
        MatchedCount = $matchedSource.Count
        CorrelationStatus = 'Unambiguous'
    }
}

function Invoke-MembershipReconciliation {
    [CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
    param(
        [Parameter(Mandatory)][AllowEmptyCollection()][object[]]$Source,
        [Parameter(Mandatory)][AllowEmptyCollection()][object[]]$Target,
        [bool]$SourceComplete = $true,
        [bool]$TargetComplete = $true,
        [switch]$Execute,
        [int]$MaxChanges = 20,
        [scriptblock]$AddMember,
        [scriptblock]$RemoveMember
    )
    if ($MaxChanges -lt 0) { throw 'MaxChanges must be non-negative.' }
    $diff = Get-MembershipDiff -Source $Source -Target $Target -SourceComplete $SourceComplete -TargetComplete $TargetComplete
    $changeCount = @($diff.ToAdd).Count + @($diff.ToRemove).Count
    if ($changeCount -gt $MaxChanges) { throw "Change threshold exceeded: $changeCount > $MaxChanges." }
    if ($Execute -and ($null -eq $AddMember -or $null -eq $RemoveMember)) { throw 'Execution requested but both AddMember and RemoveMember mutation adapters are required.' }
    $mode = if ($Execute) { 'Execute' } else { 'Preview' }
    $applied = [System.Collections.Generic.List[object]]::new()
    foreach ($member in @($diff.ToAdd)) {
        $allowed = $Execute -and $PSCmdlet.ShouldProcess($member.Key, 'Add membership')
        if ($allowed) { & $AddMember $member; $wasApplied = $true } else { $wasApplied = $false }
        [void]$applied.Add([pscustomobject]@{ Action='Add'; Key=$member.Key; Applied=$wasApplied; Mode=$mode })
    }
    foreach ($member in @($diff.ToRemove)) {
        $allowed = $Execute -and $PSCmdlet.ShouldProcess($member.Key, 'Remove membership')
        if ($allowed) { & $RemoveMember $member; $wasApplied = $true } else { $wasApplied = $false }
        [void]$applied.Add([pscustomobject]@{ Action='Remove'; Key=$member.Key; Applied=$wasApplied; Mode=$mode })
    }
    [pscustomobject]@{ Mode=$mode; SourceComplete=$SourceComplete; TargetComplete=$TargetComplete; CorrelationStatus=$diff.CorrelationStatus; Changes=@($applied); SourceCount=$diff.SourceCount; TargetCount=$diff.TargetCount; MatchedCount=$diff.MatchedCount }
}

Export-ModuleMember -Function ConvertTo-NormalizedIdentity,Get-GraphPagedCollection,Get-ProviderMembership,New-MockMembershipProvider,Get-MembershipDiff,Invoke-MembershipReconciliation
