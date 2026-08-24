Import-Module (Join-Path $PSScriptRoot '..\src\ExchangeForwardingAudit.psm1') -Force

Describe 'Exchange forwarding audit' {
    It 'rejects an inverted date window' {
        { Test-AuditDateWindow -StartDate ([datetime]'2030-02-01') -EndDate ([datetime]'2030-01-01') } | Should -Throw
    }

    It 'correlates current and historical records' {
        $current = @([pscustomobject]@{UserPrincipalName='analyst.one@brand-a.example'; ForwardingEnabled=$true; ForwardingAddress='route@example.invalid'; DeliverToMailboxAndForward=$true})
        $events = @([pscustomobject]@{UserPrincipalName='analyst.one@brand-a.example'; Timestamp='2030-06-01T12:00:00Z'; Operation='Set-MailboxForwardingAddress'})
        $result = New-ForwardingAuditReport -CurrentState $current -AuditEvents $events -StartDate ([datetime]'2030-01-01') -EndDate ([datetime]'2030-12-31')
        $result.Correlation | Should -Be 'CurrentAndHistorical'
        $result.HistoricalEventCount | Should -Be 1
    }

    It 'follows paginated provider pages' {
        $pages = @(
            [pscustomobject]@{ Items=@([pscustomobject]@{Id=1}); NextLink='page-2'; Complete=$true },
            [pscustomobject]@{ Items=@([pscustomobject]@{Id=2}); NextLink=$null; Complete=$true }
        )
        $script:index = 0
        $result = Get-PagedRecords -PageProvider { param($next) $page=$pages[$script:index]; $script:index = $script:index + 1; $page }
        $result.Items.Count | Should -Be 2
        $result.Complete | Should -BeTrue
    }

    It 'does not retry permanent validation failures' {
        $script:attempts = 0
        { Invoke-AuditRetry -Attempts 3 -BaseDelayMilliseconds 0 -Operation { $script:attempts++; throw [System.InvalidOperationException]::new('validation failed') } } | Should -Throw
        $script:attempts | Should -Be 1
    }

    It 'refuses incomplete correlation and redacts forwarding destinations by default' {
        { New-ForwardingAuditReport -CurrentState @() -AuditEvents @() -StartDate ([datetime]'2030-01-01') -EndDate ([datetime]'2030-12-31') -AuditEventsComplete:$false } | Should -Throw
        $current = @([pscustomobject]@{UserPrincipalName='analyst.one@brand-a.example'; ForwardingEnabled=$true; ForwardingAddress='route@example.invalid'})
        $report = Protect-ForwardingAuditReport -Report @(New-ForwardingAuditReport -CurrentState $current -AuditEvents @() -StartDate ([datetime]'2030-01-01') -EndDate ([datetime]'2030-12-31'))
        $report.CurrentForwardingAddress | Should -Be '[REDACTED_FORWARDING_ADDRESS]'
    }

    It 'retries transient failures' {
        $script:attempts = 0
        $result = Invoke-AuditRetry -Attempts 3 -BaseDelayMilliseconds 0 -Operation {
            $script:attempts++
            if ($script:attempts -lt 3) { throw [System.TimeoutException]::new('temporary timeout') }
            'ok'
        }
        $result | Should -Be 'ok'
        $script:attempts | Should -Be 3
    }
}
