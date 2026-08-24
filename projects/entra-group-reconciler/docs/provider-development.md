# Provider development

Implement a provider as a small object with a paged `GetPage` operation and explicit `Add`/`Remove` operations. A real Microsoft Graph adapter would pass the `@odata.nextLink` URL through the page callback and return `Items`, `NextLink`, and `Complete`; an Exchange adapter can normalize recipient properties into the same internal shape. Authentication, tenant selection, and permission checks belong outside `Invoke-MembershipReconciliation`.

The engine refuses incomplete collection, duplicate normalized identities, and ambiguous provider/address matches. These checks protect against a partial page being interpreted as a complete desired state. The mock provider and fixture runner are the only executable mutation path included here.
