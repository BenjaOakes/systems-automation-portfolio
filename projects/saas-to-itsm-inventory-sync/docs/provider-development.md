# Provider development

The core accepts page iterables from a source provider and mutation callables from a target provider. A real adapter should expose stable internal records, follow each API's pagination link until completion, classify throttling/timeouts as retryable, and return a completeness flag to the planner.

The included `MockInventoryProvider` is deliberately stateful so the execute path can be demonstrated without a network. It is not a vendor emulator. A production adapter should add provider-specific authentication outside the planner, use an idempotency key where supported, and persist the `MutationJournal` to an approved audit destination.
