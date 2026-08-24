# SaaS-to-ITSM Inventory Sync

Operational posture: `PROVIDER-READY / MUTATION-CAPABLE`. The core is reusable, dry-run is the default, and the included execute path mutates only an in-memory mock target.

## Problem and use case

SaaS inventories and ITSM/CMDBs use different names, identifiers, pagination models, and field conventions. A useful synchronizer must normalize records, explain matches, generate payloads, and make proposed changes reviewable before sending mutations.

The intended audience is integration engineers, platform teams, CMDB owners, and developers building safe SaaS-to-ITSM jobs.

## Architecture and data contract

Source and target providers return pages of mappings. Each record is normalized to `InventoryRecord(key, name, kind, attributes)`. Matching is case/whitespace/punctuation-insensitive by name, with kind differences producing updates. `build_plan` is pure and refuses incomplete collections, duplicate normalized target names, and plans above `max_changes`.

`apply_plan` enforces a second mutation-boundary threshold and requires both `dry_run=False` and `allow_mutations=True`. It records a journal and raises `PartialMutationError` with previously applied items if an adapter fails partway through.

## Installation, configuration, and usage

Python 3.10+ and the standard library are enough:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
python -m itsm_sync.cli --fixture examples/inventory.fixture.json --json
python -m itsm_sync.cli --fixture examples/inventory.fixture.json --execute --json
```

`config/config.example.json` shows `field_map` and `max_changes`. The fixture contains paginated `source_pages`, `target_pages`, and completeness flags. The first command is a dry-run; `--execute` changes only the in-memory mock and returns an explicit mutation journal.

## Provider development

Implement a source provider that yields complete pages of records with stable `id`/key, name, kind, and source attributes, and a target adapter with complete listing plus `create(payload)` and `update(target_key, payload)`. Normalize provider-specific errors so retryable timeouts, connection failures, throttles, and 5xx responses are distinguishable from validation/authentication failures. Add idempotency keys, audit retention, approvals, and reconciliation for partial failure before production use. No vendor URL, token, or employer configuration is included.

## Permissions, safety, testing, and limitations

Fixture mode needs only local file access. A live source/target adapter must document its API scopes and rate limits. Dry-run, complete-collection checks, two mutation gates, retry classification, and partial-failure journaling reduce risk but do not provide transactional semantics. Tests cover normalization, pagination, matching, payloads, retries, thresholds, mock execution, and partial failures.
