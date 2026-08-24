# Investigation workflow

Collect current mailbox forwarding state and each audit source independently. Preserve the provider continuation/completeness result, then pass only complete normalized records to `New-ForwardingAuditReport`. A current-only result can mean a historical event is outside retention; a historical-only result can mean the setting has since been removed.

The runner redacts forwarding destinations by default. Use `-IncludeForwardingAddresses` only when the report is being handled in an approved restricted location. Do not write raw audit payloads, IP addresses, user agents, tokens, or connection diagnostics to ordinary logs. Date windows are converted to UTC and the end date must be later than the start date.
