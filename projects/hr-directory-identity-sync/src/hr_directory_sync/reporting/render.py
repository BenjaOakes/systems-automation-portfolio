from __future__ import annotations

import csv
import io
import json

from ..models.records import ReconciliationPlan


def plan_as_json(plan: ReconciliationPlan, journal: list[dict[str, object]] | None = None) -> str:
    value = plan.as_dict()
    if journal is not None:
        value["mutation_journal"] = journal
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def plan_as_csv(plan: ReconciliationPlan) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=["employee_id", "action", "status", "target_id", "target_systems", "reasons", "changes"])
    writer.writeheader()
    for item in plan.items:
        writer.writerow({"employee_id": item.employee_id, "action": item.action, "status": item.status, "target_id": item.target_id or "", "target_systems": ";".join(item.target_systems), "reasons": ";".join(item.reasons), "changes": json.dumps(dict(item.changes), sort_keys=True)})
    return stream.getvalue()
