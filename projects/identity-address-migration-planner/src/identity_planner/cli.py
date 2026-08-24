from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .planner import Policy, plan_migration


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create an offline identity address migration plan.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args(argv)
    data = json.loads(args.input.read_text(encoding="utf-8"))
    policy = Policy.from_dict(json.loads(args.policy.read_text(encoding="utf-8")))
    rows = plan_migration(data["users"], policy)
    if args.csv:
        with args.csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["Status", "Reason"])
            writer.writeheader()
            writer.writerows(rows)
    if args.json or not args.csv:
        print(json.dumps(rows, indent=2, sort_keys=True))
    return 0 if all(row["Status"] != "Blocked" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
