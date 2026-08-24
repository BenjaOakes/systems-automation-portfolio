# Contributing

Keep changes small, testable, and provider-neutral where possible.

- Use synthetic identities, fictional `.example` domains, and deterministic fixtures.
- Keep read, plan, and execute phases separate.
- Preserve dry-run and `WhatIf` behavior for mutation-capable examples.
- Add tests for normalization, pagination, retries, collision handling, idempotency, and failure paths.
- Do not add `.env` files, credentials, certificates, logs, exports, state, or generated packages.
- Run the relevant project tests and the publication scanner before proposing a change.

There is intentionally no license in this preparation workspace. Licensing and ownership approval must happen before public distribution.
