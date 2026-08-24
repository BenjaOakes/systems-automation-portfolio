# Provider development

Implement `HRProvider.list_employees()` and `DirectoryProvider.list_identities()`, returning records plus a completeness boolean. A real HR adapter should page the HCM API to completion and normalize employment status without copying raw payloads into reports. A Graph adapter should preserve object ID, employee ID extension, UPN, mail, aliases, enabled state, and continuation completeness. An LDAP/AD adapter should map employee ID, mail/proxy addresses, enabled state, manager, and selected managed attributes.

Providers also implement `apply(ChangeItem)` and `verify(ChangeItem)`. Keep authentication, retry classification, rate limits, and provider-specific permission checks inside the adapter. The core should not need to know whether a provider uses Graph, LDAP, REST, or a batch API.
