# Portfolio map

The projects are organized around a common systems-engineering progression:

1. **Observe** — inspect local sessions, domains, certificates, mail routing, and directory signals.
2. **Normalize** — turn provider-shaped data into stable records with explicit identities and timestamps.
3. **Plan** — calculate diffs, migration proposals, reports, and bounded change sets.
4. **Execute safely** — keep mutation behind explicit gates, `WhatIf`/dry-run behavior, thresholds, and complete collection.
5. **Verify and retain state** — record outcomes, retry transient failures, resume idempotently, and make results reviewable.

| Pattern | Demonstrated by |
| --- | --- |
| Typed parser and privacy boundary | local-agent-observability |
| Network checks, caching, rate limiting | domain-certificate-observer |
| Current-state/history correlation | exchange-forwarding-audit |
| Paginated collection and set reconciliation | entra-group-reconciler |
| API integration and payload planning | saas-to-itsm-inventory-sync |
| Read-only reporting contracts | entra-reporting-toolbox |
| Phased idempotent orchestration | idempotent-identity-workflow-engine |
| Collision-aware policy planning | identity-address-migration-planner |
| HR-to-hybrid identity reconciliation | hr-directory-identity-sync |
