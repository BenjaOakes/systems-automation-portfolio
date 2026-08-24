# Workflow architecture

The engine separates orchestration from provider operations. Each phase has an idempotent pre-check, a mutation operation, and a post-step verification. State is written atomically after each verified phase, so a rerun can resume without repeating completed work. A stale completed phase is re-verified against the provider rather than trusted from the state file alone.

The provider contract in the mock is a set of scriptblocks (`GetIdentity`, `GetGroups`, `RemoveGroup`, and so on). A real adapter can implement the same contract for a directory, mailbox, or device system, but should be designed with its own authorization, throttling, rollback, and approval review. Automatic rollback is deliberately not attempted; the state records a human-review rollback plan instead.
