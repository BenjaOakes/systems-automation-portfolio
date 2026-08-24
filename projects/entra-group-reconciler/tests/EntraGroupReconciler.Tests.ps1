Import-Module (Join-Path $PSScriptRoot '..\src\EntraGroupReconciler.psm1') -Force

Describe 'Entra group reconciler' {
    It 'prefers provider correlation and supports the same identity represented as SMTP' {
        $source = @([pscustomobject]@{Id='user-1'; UserPrincipalName='member.one@brand-a.example'})
        $target = @([pscustomobject]@{PrimarySmtpAddress='member.one@brand-a.example'})
        $diff = Get-MembershipDiff -Source $source -Target $target
        $diff.ToAdd.Count | Should -Be 0
        $diff.ToRemove.Count | Should -Be 0
        $diff.MatchedCount | Should -Be 1
    }

    It 'detects duplicate normalized identities instead of overwriting them' {
        $source = @(
            [pscustomobject]@{UserPrincipalName='one@brand-a.example'},
            [pscustomobject]@{Mail='ONE@brand-a.example'}
        )
        { Get-MembershipDiff -Source $source -Target @() } | Should -Throw '*Duplicate normalized identity*'
    }

    It 'blocks conflicting provider and SMTP correlation as ambiguous' {
        $source = @([pscustomobject]@{Id='user-1'; UserPrincipalName='one@brand-a.example'})
        $target = @([pscustomobject]@{Id='user-2'; PrimarySmtpAddress='one@brand-a.example'})
        { Get-MembershipDiff -Source $source -Target $target } | Should -Throw '*Ambiguous identity correlation*'
    }

    It 'calculates true additions and removals deterministically' {
        $source = @([pscustomobject]@{UserPrincipalName='one@brand-a.example'}, [pscustomobject]@{UserPrincipalName='two@brand-a.example'})
        $target = @([pscustomobject]@{PrimarySmtpAddress='one@brand-a.example'}, [pscustomobject]@{PrimarySmtpAddress='old@brand-a.example'})
        $diff = Get-MembershipDiff -Source $source -Target $target
        $diff.ToAdd.Count | Should -Be 1
        $diff.ToRemove.Count | Should -Be 1
        $diff.ToAdd[0].Key | Should -Be 'smtp:two@brand-a.example'
        $diff.ToRemove[0].Key | Should -Be 'smtp:old@brand-a.example'
    }

    It 'fails closed when either collection is incomplete' {
        { Get-MembershipDiff -Source @() -Target @() -SourceComplete $false } | Should -Throw '*incomplete*'
        { Get-MembershipDiff -Source @() -Target @() -TargetComplete $false } | Should -Throw '*incomplete*'
    }

    It 'enforces the maximum-change threshold' {
        $source = @([pscustomobject]@{UserPrincipalName='one@brand-a.example'}, [pscustomobject]@{UserPrincipalName='two@brand-a.example'})
        { Invoke-MembershipReconciliation -Source $source -Target @() -MaxChanges 1 } | Should -Throw '*Change threshold exceeded*'
    }

    It 'previews without invoking mutation adapters' {
        $called = $false
        $source = @([pscustomobject]@{UserPrincipalName='one@brand-a.example'})
        $result = Invoke-MembershipReconciliation -Source $source -Target @() -AddMember { $script:called = $true } -RemoveMember { $script:called = $true }
        $result.Mode | Should -Be 'Preview'
        $result.Changes[0].Applied | Should -BeFalse
        $called | Should -BeFalse
    }

    It 'fails clearly when Execute has no mutation adapters' {
        $source = @([pscustomobject]@{UserPrincipalName='one@brand-a.example'})
        { Invoke-MembershipReconciliation -Source $source -Target @() -Execute } | Should -Throw '*mutation adapters are required*'
    }

    It 'collects all pages through the mock provider contract' {
        $provider = New-MockMembershipProvider -Members @(
            [pscustomobject]@{Id='one'},
            [pscustomobject]@{Id='two'},
            [pscustomobject]@{Id='three'}
        ) -PageSize 2
        $collection = Get-ProviderMembership -Provider $provider -Operation GetPage
        $collection.Items.Count | Should -Be 3
        $collection.Complete | Should -BeTrue
        $provider.Calls.Count | Should -Be 2
    }
}
