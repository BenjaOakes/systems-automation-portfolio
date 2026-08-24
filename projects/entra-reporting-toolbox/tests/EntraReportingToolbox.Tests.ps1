Import-Module (Join-Path $PSScriptRoot '..\src\EntraReportingToolbox.psm1') -Force

BeforeAll {
    $users = @(
    [pscustomobject]@{Id='user-001'; DisplayName='Aster Example'; UserPrincipalName='user.one@brand-a.example'; Mail='user.one@brand-a.example'; AccountEnabled=$true; LastSignInDateTime='2029-12-01T00:00:00Z'},
    [pscustomobject]@{Id='user-002'; DisplayName='Blue Sample'; UserPrincipalName='user.two@brand-b.example'; Mail='user.two@brand-b.example'; AccountEnabled=$false; LastSignInDateTime=$null}
    )
}

Describe 'Entra reporting toolbox' {
    It 'reports domains and statuses' {
        (Get-UserStatusReport -Users $users).Count | Should -Be 2
        (Get-UserDomainReport -Users $users | Where-Object Domain -eq 'brand-a.example').UserCount | Should -Be 1
    }

    It 'resolves object IDs without mutation' {
        (Resolve-EntraObjectId -Objects $users -Query 'user.one@brand-a.example').Status | Should -Be 'Found'
        (Resolve-EntraObjectId -Objects $users -Query 'user.one@brand-a.example').Id | Should -Be 'user-001'
    }

    It 'distinguishes missing account state and ambiguous object lookup' {
        $missing = [pscustomobject]@{Id='user-003'; UserPrincipalName='missing@brand-a.example'}
        (Get-UserStatusReport -Users @($missing)).AccountEnabled | Should -BeNullOrEmpty
        (Get-UserStatusReport -Users @($missing)).AccountStatus | Should -Be 'Missing'
        $ambiguous = Resolve-EntraObjectId -Objects @($users + [pscustomobject]@{Id='user-003'; DisplayName='user.one@brand-a.example'}) -Query 'user.one@brand-a.example'
        $ambiguous.Status | Should -Be 'Ambiguous'
        $ambiguous.MatchCount | Should -Be 2
    }

    It 'reports inactive users with no sign-in data' {
        (Get-InactiveUserReport -Users $users -InactiveBefore ([datetime]'2030-01-01')).Reason | Should -Contain 'NoSignInRecorded'
    }

    It 'joins group membership and application sign-ins' {
        $group = @([pscustomobject]@{Id='group-001'; DisplayName='Synthetic Operators'; Members=@([pscustomobject]@{Id='user-001'})})
        (Get-GroupMembershipReport -Groups $group -Users $users).UserPrincipalName | Should -Be 'user.one@brand-a.example'
        $app = @([pscustomobject]@{AppId='app-001'; DisplayName='Fixture Inventory'})
        $event = @([pscustomobject]@{AppId='app-001'; CreatedDateTime='2030-01-01'; UserPrincipalName='user.one@brand-a.example'; Status='Success'; FailureReason=$null})
        (Get-EnterpriseAppSignInReport -Applications $app -SignInEvents $event).AppDisplayName | Should -Be 'Fixture Inventory'
    }

    It 'keeps Graph-style pagination separate from report shaping' {
        $pages = @(
            [pscustomobject]@{value=@([pscustomobject]@{Id='one'}); '@odata.nextLink'='next'},
            [pscustomobject]@{value=@([pscustomobject]@{Id='two'}); '@odata.nextLink'=$null}
        )
        $script:index = 0
        $collection = Get-EntraGraphPagedCollection -PageProvider { param($next) $page=$pages[$script:index]; $script:index++; $page }
        $collection.Items.Count | Should -Be 2
        $collection.Complete | Should -BeTrue
    }
}
