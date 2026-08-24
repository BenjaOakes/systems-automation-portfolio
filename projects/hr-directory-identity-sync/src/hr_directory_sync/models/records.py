from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class EmployeeRecord:
    employee_id: str
    given_name: str
    surname: str
    work_email: str
    department: str
    brand: str
    employee_type: str
    status: str
    manager_employee_id: str | None = None
    source_row: int = 0
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class DirectoryRecord:
    object_id: str
    system: str
    employee_id: str
    display_name: str
    user_principal_name: str
    mail: str
    enabled: bool
    attributes: Mapping[str, Any] = field(default_factory=dict)
    systems: tuple[str, ...] = ()

    @property
    def match_addresses(self) -> tuple[str, ...]:
        values = [self.user_principal_name, self.mail, *self.attributes.get("aliases", [])]
        return tuple(sorted({str(value).strip().casefold() for value in values if str(value or "").strip()}))


@dataclass(frozen=True)
class ChangeItem:
    employee_id: str
    action: str
    status: str
    target_id: str | None
    target_systems: tuple[str, ...]
    desired: Mapping[str, Any]
    changes: Mapping[str, Any]
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "employee_id": self.employee_id,
            "action": self.action,
            "status": self.status,
            "target_id": self.target_id,
            "target_systems": list(self.target_systems),
            "desired": dict(self.desired),
            "changes": dict(self.changes),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ReconciliationPlan:
    items: tuple[ChangeItem, ...]
    source_complete: bool = True
    directory_complete: bool = True

    @property
    def changes(self) -> tuple[ChangeItem, ...]:
        return tuple(item for item in self.items if item.action not in {"NoChange", "Blocked"} and item.status not in {"Blocked", "ReviewRequired"})

    def summary(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for item in self.items:
            result[item.status] = result.get(item.status, 0) + 1
        return dict(sorted(result.items()))

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_complete": self.source_complete,
            "directory_complete": self.directory_complete,
            "summary": self.summary(),
            "items": [item.as_dict() for item in self.items],
        }
