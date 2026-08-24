from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable, Mapping, Sequence

from ..models.records import ChangeItem, DirectoryRecord, EmployeeRecord
from ..normalization.normalize import normalize_employee


def _directory_record(raw: Mapping[str, Any], system: str) -> DirectoryRecord:
    attributes = dict(raw)
    aliases = attributes.get("aliases", []) or []
    if isinstance(aliases, str):
        aliases = [item.strip() for item in aliases.split(";") if item.strip()]
    attributes["aliases"] = list(aliases)
    return DirectoryRecord(
        object_id=str(raw.get("object_id", raw.get("id", f"{system}-unknown"))),
        system=system,
        employee_id=str(raw.get("employee_id", "")).strip(),
        display_name=str(raw.get("display_name", "")),
        user_principal_name=str(raw.get("user_principal_name", raw.get("upn", ""))).strip().casefold(),
        mail=str(raw.get("mail", "")).strip().casefold(),
        enabled=bool(raw.get("enabled", raw.get("account_enabled", True))),
        attributes=attributes,
        systems=(system,),
    )


class MockHRProvider:
    def __init__(self, rows: Iterable[Mapping[str, Any] | EmployeeRecord], complete: bool = True) -> None:
        self._employees = [row if isinstance(row, EmployeeRecord) else normalize_employee(row, index + 2) for index, row in enumerate(rows)]
        self.complete = complete

    def list_employees(self) -> tuple[Sequence[EmployeeRecord], bool]:
        return tuple(self._employees), self.complete


class MockDirectoryProvider:
    system_name = "mock"

    def __init__(self, records: Iterable[Mapping[str, Any]], system_name: str, complete: bool = True) -> None:
        self.system_name = system_name
        self.records: list[DirectoryRecord] = [_directory_record(record, system_name) for record in records]
        self.complete = complete
        self.calls: list[str] = []

    def list_identities(self) -> tuple[Sequence[DirectoryRecord], bool]:
        return tuple(self.records), self.complete

    def apply(self, item: ChangeItem) -> None:
        self.calls.append(f"{item.action}:{item.employee_id}")
        matches = [index for index, record in enumerate(self.records) if record.employee_id == item.employee_id or record.object_id == item.target_id]
        desired = dict(item.desired)
        if matches:
            index = matches[0]
            current = self.records[index]
            self.records[index] = replace(
                current,
                display_name=str(desired.get("display_name", current.display_name)),
                user_principal_name=str(desired.get("user_principal_name", current.user_principal_name)),
                mail=str(desired.get("mail", current.mail)),
                enabled=bool(desired.get("enabled", current.enabled)),
                attributes={**dict(current.attributes), **desired},
            )
        else:
            self.records.append(_directory_record({"object_id": f"{self.system_name}-{item.employee_id}", **desired}, self.system_name))

    def verify(self, item: ChangeItem) -> bool:
        matches = [record for record in self.records if record.employee_id == item.employee_id]
        if not matches:
            return False
        record = matches[0]
        desired = item.desired
        return record.user_principal_name == desired.get("user_principal_name") and record.mail == desired.get("mail") and record.enabled == desired.get("enabled")


class MockEntraProvider(MockDirectoryProvider):
    def __init__(self, records: Iterable[Mapping[str, Any]], complete: bool = True) -> None:
        super().__init__(records, "entra", complete)


class MockADProvider(MockDirectoryProvider):
    def __init__(self, records: Iterable[Mapping[str, Any]], complete: bool = True) -> None:
        super().__init__(records, "ad", complete)


def collect_directory(*providers: MockDirectoryProvider) -> tuple[list[DirectoryRecord], bool]:
    """Merge the same hybrid identity across AD and Entra for one plan.

    A matching employee ID across systems is one identity, not an ambiguity.
    Email-only duplicates remain separate and are intentionally surfaced by
    the reconciliation engine.
    """
    all_records: list[DirectoryRecord] = []
    complete = True
    for provider in providers:
        records, provider_complete = provider.list_identities()
        all_records.extend(records)
        complete = complete and provider_complete
    grouped: dict[str, list[DirectoryRecord]] = {}
    merged: list[DirectoryRecord] = []
    for record in all_records:
        if record.employee_id:
            grouped.setdefault(record.employee_id, []).append(record)
        else:
            merged.append(record)
    for employee_id, records in grouped.items():
        first = records[0]
        systems = tuple(sorted({system for record in records for system in (record.systems or (record.system,))}))
        merged.append(replace(first, systems=systems, attributes={**dict(first.attributes), "systems": list(systems)}))
    return sorted(merged, key=lambda record: (record.employee_id, record.object_id)), complete
