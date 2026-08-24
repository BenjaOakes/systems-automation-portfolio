# Reconciliation and idempotency

Only managed attributes are compared. Unmanaged directory attributes are carried through by a provider and are not overwritten blindly. A plan item is `NoChange` when all managed values already match, `Create` for a missing identity, `Update` for attribute changes, and `Disable` for a termination-only enabled-state change.

The default is plan/dry-run. Execution requires both `--execute` and the in-memory mock providers in this public implementation. Each mutation is followed by provider verification; a multi-system failure returns a partial journal and stops. Re-running a successful mock execution produces `NoChange` for the same records.
