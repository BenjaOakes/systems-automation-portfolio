from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from .models.records import ReconciliationPlan
from .policy.rules import Policy
from .providers.mock import MockADProvider, MockEntraProvider, MockHRProvider, collect_directory
from .reconciliation.engine import apply_plan, build_plan
from .reporting.render import plan_as_csv, plan_as_json


def _read_employees(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_directory(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("entra", [])), list(data.get("ad", []))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan HR-to-hybrid-directory identity reconciliation using synthetic/mock providers.")
    parser.add_argument("--employees", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--csv", action="store_true")
    parser.add_argument("--execute", action="store_true", help="Apply only to the included in-memory mock providers.")
    parser.add_argument("--max-changes", type=int, default=25)
    args = parser.parse_args(argv)
    employees = _read_employees(args.employees)
    entra_rows, ad_rows = _read_directory(args.directory)
    policy = Policy.from_mapping(json.loads(args.policy.read_text(encoding="utf-8")))
    hr = MockHRProvider(employees)
    entra = MockEntraProvider(entra_rows)
    ad = MockADProvider(ad_rows)
    hr_rows, hr_complete = hr.list_employees()
    directory, directory_complete = collect_directory(entra, ad)
    plan = build_plan(hr_rows, directory, policy, source_complete=hr_complete, directory_complete=directory_complete)
    journal = apply_plan(plan, entra_provider=entra, ad_provider=ad, dry_run=not args.execute, execute=args.execute, max_changes=args.max_changes)
    if args.csv:
        output = plan_as_csv(plan)
    else:
        output = plan_as_json(plan, journal)
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 1 if any(item.status in {"Blocked", "ReviewRequired"} for item in plan.items) else 0


if __name__ == "__main__":
    raise SystemExit(main())
