Import-Module (Join-Path $PSScriptRoot '..\src\IdentityWorkflowEngine.psm1') -Force

Describe 'Idempotent identity workflow engine' {
    BeforeEach {
        $root = Join-Path $PSScriptRoot '.test-state'
        if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
        New-Item -ItemType Directory -Path $root -Force | Out-Null
    }
    AfterAll {
        $root = Join-Path $PSScriptRoot '.test-state'
        if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
    }

    It 'returns a preview without provider mutations' {
        $provider = New-MockIdentityProvider
        $root = Join-Path $PSScriptRoot '.test-state'
        $result = Invoke-IdentityWorkflow -Provider $provider -IdentityId 'fixture-user-001' -StatePath (Join-Path $root 'preview.json')
        $result.Mode | Should -Be 'Preview'
        $provider.Calls.Count | Should -Be 0
        Test-Path -LiteralPath (Join-Path $root 'preview.json') | Should -BeFalse
    }

    It 'does not persist state under Execute WhatIf' {
        $provider = New-MockIdentityProvider
        $path = Join-Path (Join-Path $PSScriptRoot '.test-state') 'whatif.json'
        $result = Invoke-IdentityWorkflow -Provider $provider -IdentityId 'fixture-user-001' -StatePath $path -Execute -WhatIf -Confirm:$false
        $result.Status | Should -Be 'WhatIf'
        $provider.Calls.Count | Should -Be 0
        Test-Path -LiteralPath $path | Should -BeFalse
    }

    It 'only persists a preview when explicitly requested' {
        $provider = New-MockIdentityProvider
        $path = Join-Path (Join-Path $PSScriptRoot '.test-state') 'preview-output.json'
        $result = Invoke-IdentityWorkflow -Provider $provider -IdentityId 'fixture-user-001' -StatePath $path -WritePreview
        $result.StatePersisted | Should -BeTrue
        Test-Path -LiteralPath $path | Should -BeTrue
    }

    It 'blocks protected identities' {
        $provider = New-MockIdentityProvider -IdentityId 'fixture-break-glass'
        { Invoke-IdentityWorkflow -Provider $provider -IdentityId 'fixture-break-glass' -StatePath (Join-Path (Join-Path $PSScriptRoot '.test-state') 'protected.json') -ProtectedIdentities 'fixture-break-glass' } | Should -Throw
    }

    It 'executes mock phases and resumes idempotently' {
        $provider = New-MockIdentityProvider
        $path = Join-Path (Join-Path $PSScriptRoot '.test-state') 'state.json'
        $first = Invoke-IdentityWorkflow -Provider $provider -IdentityId 'fixture-user-001' -StatePath $path -Execute -Confirm:$false
        $first.Status | Should -Be 'Completed'
        $calls = $provider.Calls.Count
        $second = Invoke-IdentityWorkflow -Provider $provider -IdentityId 'fixture-user-001' -StatePath $path -Execute -Confirm:$false
        $second.Status | Should -Be 'Completed'
        $provider.Calls.Count | Should -Be $calls
    }

    It 'rejects state files for another identity' {
        $path = Join-Path (Join-Path $PSScriptRoot '.test-state') 'wrong-identity.json'
        $state = [pscustomobject]@{SchemaVersion=1; IdentityId='fixture-user-002'; Status='Completed'; CompletedSteps=@(); Attempts=@{}; RollbackPlan=@(); UpdatedUtc=[datetime]::UtcNow}
        Write-WorkflowState -State $state -Path $path
        { Read-WorkflowState -Path $path -IdentityId 'fixture-user-001' } | Should -Throw '*does not match*'
    }

    It 'retries transient failures but not permanent validation failures' {
        $script:workflowTransientCalls = 0
        Invoke-WorkflowOperation -Attempts 3 -Operation {
            $script:workflowTransientCalls++
            if ($script:workflowTransientCalls -lt 2) {
                $error = [System.TimeoutException]::new('transient timeout')
                $error.Data['Retryable'] = $true
                throw $error
            }
        }
        $script:workflowTransientCalls | Should -Be 2

        $script:workflowPermanentCalls = 0
        { Invoke-WorkflowOperation -Attempts 3 -Operation { $script:workflowPermanentCalls++; throw [System.InvalidOperationException]::new('validation failed') } } | Should -Throw
        $script:workflowPermanentCalls | Should -Be 1
    }

    It 'fails and persists state when post-step verification fails' {
        $provider = New-MockIdentityProvider
        $provider.Operations.SuspendIdentity = { param($id) [void]$provider.Calls.Add("SuspendIdentity:$id") }
        $path = Join-Path (Join-Path $PSScriptRoot '.test-state') 'verification.json'
        { Invoke-IdentityWorkflow -Provider $provider -IdentityId 'fixture-user-001' -StatePath $path -Execute -Confirm:$false } | Should -Throw '*Post-step verification failed*'
        (Read-WorkflowState -Path $path -IdentityId 'fixture-user-001').Status | Should -Be 'Failed'
    }
}
