from __future__ import annotations

from typing import Iterable, Mapping, Protocol, Sequence

from ..models.records import ChangeItem, DirectoryRecord, EmployeeRecord


class HRProvider(Protocol):
    def list_employees(self) -> tuple[Sequence[EmployeeRecord], bool]: ...


class DirectoryProvider(Protocol):
    system_name: str

    def list_identities(self) -> tuple[Sequence[DirectoryRecord], bool]: ...

    def apply(self, item: ChangeItem) -> None: ...

    def verify(self, item: ChangeItem) -> bool: ...
