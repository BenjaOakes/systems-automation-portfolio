# Authentication and permissions

Reporting functions are pure transformations over objects supplied by the caller. They do not call `Connect-MgGraph` and do not store credentials. For a live adapter, authenticate in the calling script using an approved delegated flow, certificate credential from the local certificate store, managed identity, or another organization-approved secret broker.

Typical least-privilege permissions depend on the report: `User.Read.All` for user status/domain data, `Group.Read.All` for group membership, and an appropriate audit-log read permission for sign-in reporting. Verify current Microsoft Graph permission requirements for the selected endpoint before deployment. Never commit tokens, client secrets, private keys, or tenant-specific configuration.

`Invoke-EntraGraphReadOnly` is a small optional boundary around `Invoke-MgGraphRequest`. It is intentionally separate from report shaping so authentication, pagination, throttling, and data-retention choices remain visible to the operator.
