from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Iterable, Mapping, Sequence

from ..models.records import ChangeItem, DirectoryRecord, EmployeeRecord, ReconciliationPlan
from ..normalization.normalize import normalize_employee
from ..policy.rules import Policy, PolicyError


def _as_employee(value: EmployeeRecord | Mapping[str, Any], index: int) -> EmployeeRecord:
    return value if isinstance(value, EmployeeRecord) else normalize_employee(value, index + 2)


def _address(value: Any) -> str:
    return str(value or "").strip().casefold()


def _find_candidates(employee: EmployeeRecord, directory: Sequence[DirectoryRecord]) -> list[DirectoryRecord]:
    by_id = [record for record in directory if employee.employee_id and record.employee_id == employee.employee_id]
    if by_id:
        return by_id
    return [record for record in directory if employee.work_email in record.match_addresses]


def build_plan(
    employees: Iterable[EmployeeRecord | Mapping[str, Any]],
    directory: Iterable[DirectoryRecord],
    policy: Policy,
    *,
    source_complete: bool = True,
    directory_complete: bool = True,
) -> ReconciliationPlan:
    employees_list = [_as_employee(value, index) for index, value in enumerate(employees)]
    directory_list = list(directory)
    if not source_complete or not directory_complete:
        # A partial HR feed or directory page cannot safely prove a new hire,
        # termination, or address collision is absent.
        raise ValueError("HR and directory collections must be complete")
    employee_id_counts: dict[str, int] = {}
    for employee in employees_list:
        employee_id_counts[employee.employee_id] = employee_id_counts.get(employee.employee_id, 0) + 1
    all_addresses = {address for record in directory_list for address in record.match_addresses}
    items: list[ChangeItem] = []
    for employee in employees_list:
        reasons = list(employee.errors)
        review: list[str] = []
        desired: dict[str, Any] = {}
        try:
            desired = policy.desired_attributes(employee)
        except PolicyError as exc:
            reasons.append(str(exc))
        if employee_id_counts.get(employee.employee_id, 0) > 1:
            reasons.append("duplicate_hr_employee_id")
        if employee.manager_employee_id and employee.manager_employee_id not in employee_id_counts:
            review.append("missing_manager")
        candidates = _find_candidates(employee, directory_list) if not reasons or not employee.errors else []
        if len(candidates) > 1:
            reasons.append("ambiguous_directory_match")
        candidate = candidates[0] if len(candidates) == 1 else None
        if candidate and employee.employee_id and candidate.employee_id and candidate.employee_id != employee.employee_id:
            # An email match to a different known employee is a collision or
            # stale HR identity, not permission to update the other person.
            reasons.append("identity_key_conflict")
        target_addresses = {_address(desired.get("user_principal_name")), _address(desired.get("mail"))}
        candidate_addresses = set(candidate.match_addresses) if candidate and candidate.employee_id == employee.employee_id else set()
        if target_addresses & (all_addresses - candidate_addresses):
            reasons.append("upn_or_mail_collision")
        if candidate:
            current_values = {
                "display_name": candidate.display_name,
                "department": candidate.attributes.get("department", ""),
                "brand": candidate.attributes.get("brand", ""),
                "employee_type": candidate.attributes.get("employee_type", ""),
                "manager_employee_id": candidate.attributes.get("manager_employee_id"),
                "user_principal_name": candidate.user_principal_name,
                "mail": candidate.mail,
                "enabled": candidate.enabled,
                "groups": candidate.attributes.get("groups", []),
            }
            changes = {name: desired.get(name) for name in policy.managed_attributes if current_values.get(name) != desired.get(name)}
            action = "Disable" if changes.keys() == {"enabled"} and desired.get("enabled") is False else ("Update" if changes else "NoChange")
            target_id = candidate.object_id
            target_systems = candidate.systems or (candidate.system,)
        else:
            changes = dict(desired)
            action = "Create"
            target_id = None
            target_systems = ("entra", "ad")
        if reasons:
            status = "Blocked"
        elif review:
            status = "ReviewRequired"
        else:
            status = action
        items.append(ChangeItem(employee.employee_id, action, status, target_id, tuple(sorted(target_systems)), desired, changes, tuple(sorted(set(reasons + review)))))
    return ReconciliationPlan(tuple(sorted(items, key=lambda item: (item.employee_id, item.action))), source_complete, directory_complete)


def apply_plan(
    plan: ReconciliationPlan,
    *,
    entra_provider: Any,
    ad_provider: Any,
    dry_run: bool = True,
    execute: bool = False,
    max_changes: int = 25,
    attempts: int = 3,
    base_delay: float = 0.0,
) -> list[dict[str, Any]]:
    """Apply only executable plan items after explicit dry-run and execute gates."""
    changes = list(plan.changes)
    if len(changes) > max_changes:
        raise ValueError(f"change threshold exceeded: {len(changes)} > {max_changes}")
    journal: list[dict[str, Any]] = []
    if dry_run or not execute:
        return [{"employee_id": item.employee_id, "action": item.action, "applied": False, "reason": "dry_run_or_execute_gate"} for item in plan.items]
    providers = {"entra": entra_provider, "ad": ad_provider}
    for item in plan.items:
        if item.status in {"Blocked", "ReviewRequired", "NoChange"}:
            journal.append({"employee_id": item.employee_id, "action": item.action, "applied": False, "reason": item.status})
            continue
        applied_systems: list[str] = []
        try:
            for system in item.target_systems:
                provider = providers[system]
                last_error: Exception | None = None
                for attempt in range(1, max(1, attempts) + 1):
                    try:
                        provider.apply(item)
                        if not provider.verify(item):
                            raise RuntimeError(f"post_step_verification_failed:{system}")
                        last_error = None
                        break
                    except (TimeoutError, ConnectionError) as exc:
                        last_error = exc
                        if attempt < attempts and base_delay:
                            time.sleep(base_delay * (2 ** (attempt - 1)))
                if last_error:
                    raise last_error
                applied_systems.append(system)
        except Exception as exc:  # keep a reviewable journal if the second system fails
            journal.append({"employee_id": item.employee_id, "action": item.action, "applied": False, "partial_systems": applied_systems, "error": str(exc)})
            raise RuntimeError(f"partial_or_failed_apply:{item.employee_id}") from exc
        journal.append({"employee_id": item.employee_id, "action": item.action, "applied": True, "systems": applied_systems})
    return journal
