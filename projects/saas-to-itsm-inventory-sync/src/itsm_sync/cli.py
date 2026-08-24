from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import MockInventoryProvider, MutationJournal, SyncConfig, apply_plan, build_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a dry-run SaaS to ITSM inventory plan.")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--config", type=Path, help="Optional JSON settings for field_map and max_changes.")
    parser.add_argument("--execute", action="store_true", help="Mutate only the in-memory mock target; never a live service.")
    parser.add_argument("--output", type=Path, help="Write the serialized plan/journal to a file.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    data = json.loads(args.fixture.read_text(encoding="utf-8"))
    settings = json.loads(args.config.read_text(encoding="utf-8")) if args.config else data
    sync_config = SyncConfig(
        field_map=settings.get("field_map", {"name": "name", "kind": "type"}),
        max_changes=int(settings.get("max_changes", 100)),
    )
    plan = build_plan(data["source_pages"], data["target_pages"], sync_config, source_complete=data.get("source_complete", True), target_complete=data.get("target_complete", True))
    journal = MutationJournal()
    target = MockInventoryProvider(data["target_pages"])
    applied = apply_plan(plan, dry_run=not args.execute, allow_mutations=args.execute, max_changes=sync_config.max_changes, create=target.create if args.execute else None, update=target.update if args.execute else None, journal=journal)
    output = [{"action": item.action, "source_key": item.source.key, "target_key": item.target_key, "payload": dict(item.payload), "reason": item.reason, "applied": next((entry["applied"] for entry in applied if entry["key"] == item.source.key), False)} for item in plan]
    result = {"mode": "execute-mock" if args.execute else "dry-run", "items": output, "mutation_journal": journal.records}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for item in output:
            print(f"{item['action']:9} {item['source_key']:20} {item['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
