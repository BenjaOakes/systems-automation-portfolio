# Security policy

These projects are educational and operationally cautious reference implementations. They are not a substitute for a provider's security review, least-privilege design, change approval, or incident-response process.

Please do not submit secrets, real directory exports, mailbox data, audit records, transcripts, employee information, private keys, certificates, or production configuration. Use synthetic fixtures and fictional `.example` domains.

Before publishing a working tree, run:

```powershell
pwsh -NoProfile -File .\tools\Invoke-PublicationScan.ps1 -Path . -OutputPath .\publication-scan.json
```

The scanner reports indicators for human review; it does not delete or rewrite files.

## Reporting a concern

For a suspected security issue, remove any sensitive local copy, preserve only the minimum safe reproduction, and document the affected project and file without including the secret itself. Review provider permissions and ownership before distributing any connector implementation.
