@{
    AuthenticationMode = 'DelegatedInteractive'
    TenantId = 'tenant-example-id'
    GraphScopes = @('User.Read.All', 'Group.Read.All', 'AuditLog.Read.All')
    OutputFormat = 'Json'
}
