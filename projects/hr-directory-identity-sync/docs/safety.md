# Safety

This project is offline-first and defaults to a plan. No live providers are included. Completeness is required before planning, unknown business policy is blocked, ambiguous identities are blocked, and change counts are bounded at the mutation boundary. Terminations are represented as explicit disabled-state changes rather than hidden deletion.

Before implementing a live adapter, establish approval, protected identities, least-privilege permissions, dry-run review, audit retention, rollback/recovery, and a test tenant or isolated directory. Treat HR data, directory attributes, manager relationships, and group membership as sensitive personal and security information.
