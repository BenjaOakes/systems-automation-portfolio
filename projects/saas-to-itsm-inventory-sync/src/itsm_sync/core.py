"""Pure synchronization planning functions and guarded adapter helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import time
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class InventoryRecord:
    key: str
    name: str
    kind: str = "application"
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SyncConfig:
    field_map: Mapping[str, str] = field(default_factory=lambda: {"name": "name", "kind": "type"})
    max_changes: int = 100
    require_complete_collection: bool = True


class InventoryProvider(Protocol):
    """Contract implemented by a SaaS source or ITSM target adapter."""

    def list_pages(self) -> Iterable[Iterable[Mapping[str, Any]]]: ...


class MutationJournal:
    """In-memory journal that a caller can serialize to an audit sink."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(self, **values: Any) -> None:
        self.records.append(dict(values))


class MockInventoryProvider:
    """A deterministic target adapter for demonstrations and offline tests.

    It intentionally exposes the same create/update shape a real ITSM adapter
    would provide, while keeping all state inside the caller's process.
    """

    def __init__(self, pages: Iterable[Iterable[Mapping[str, Any]]]) -> None:
        self.records: dict[str, dict[str, Any]] = {
            str(record.get("id") or record.get("key") or normalize_name(str(record.get("name", "")))): dict(record)
            for page in pages for record in page
        }

    def list_pages(self) -> list[list[Mapping[str, Any]]]:
        return [[dict(record) for record in self.records.values()]]

    def create(self, payload: Mapping[str, Any]) -> str:
        key = str(payload.get("key") or normalize_name(str(payload.get("name", ""))))
        self.records[key] = {"id": key, **dict(payload)}
        return key

    def update(self, key: str, payload: Mapping[str, Any]) -> None:
        if key not in self.records:
            raise KeyError(f"target record does not exist: {key}")
        self.records[key].update(dict(payload))


@dataclass(frozen=True)
class PlanItem:
    action: str
    source: InventoryRecord
    target_key: str | None
    payload: Mapping[str, Any]
    reason: str


class MutationNotAllowed(RuntimeError):
    pass


class PartialMutationError(RuntimeError):
    """An adapter failed after zero or more earlier plan items were applied."""

    def __init__(self, message: str, applied: Sequence[Mapping[str, Any]]) -> None:
        super().__init__(message)
        self.applied = list(applied)


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()


def flatten_pages(pages: Iterable[Iterable[Mapping[str, Any]]]) -> list[Mapping[str, Any]]:
    """Flatten provider pages without assuming a page-size or SDK type."""
    return [record for page in pages for record in page]


def to_record(raw: Mapping[str, Any], *, default_kind: str = "application") -> InventoryRecord:
    key = str(raw.get("id") or raw.get("key") or normalize_name(str(raw.get("name", ""))))
    return InventoryRecord(key=key, name=str(raw.get("name", "")), kind=str(raw.get("kind", default_kind)), attributes=dict(raw))


def build_payload(source: InventoryRecord, field_map: Mapping[str, str]) -> dict[str, Any]:
    values = {"key": source.key, "name": source.name, "kind": source.kind, **source.attributes}
    return {target: values.get(source_field) for source_field, target in field_map.items()}


def build_plan(
    source_pages: Iterable[Iterable[Mapping[str, Any]]],
    target_pages: Iterable[Iterable[Mapping[str, Any]]],
    config: SyncConfig | None = None,
    *,
    source_complete: bool = True,
    target_complete: bool = True,
) -> list[PlanItem]:
    config = config or SyncConfig()
    if config.require_complete_collection and (not source_complete or not target_complete):
        # A missing page can look like a large deletion. Refusing to plan is
        # safer than allowing an incomplete inventory to drive mutations.
        raise ValueError("source and target collections must be complete")
    source = [to_record(item) for item in flatten_pages(source_pages)]
    target = [to_record(item, default_kind="service") for item in flatten_pages(target_pages)]
    by_name: dict[str, list[InventoryRecord]] = {}
    for item in target:
        normalized = normalize_name(item.name)
        if normalized:
            by_name.setdefault(normalized, []).append(item)
    duplicate_names = sorted(name for name, matches in by_name.items() if len(matches) > 1)
    if duplicate_names:
        raise ValueError(f"ambiguous normalized target name(s): {', '.join(duplicate_names)}")
    unique_targets = {name: matches[0] for name, matches in by_name.items()}
    plan: list[PlanItem] = []
    for item in sorted(source, key=lambda record: (normalize_name(record.name), record.key)):
        match = unique_targets.get(normalize_name(item.name))
        if not match:
            plan.append(PlanItem("create", item, None, build_payload(item, config.field_map), "source_not_in_target"))
        elif match.kind != item.kind:
            plan.append(PlanItem("update", item, match.key, build_payload(item, config.field_map), "normalized_attributes_differ"))
        else:
            plan.append(PlanItem("unchanged", item, match.key, {}, "matching_name_and_kind"))
    changes = [item for item in plan if item.action != "unchanged"]
    if len(changes) > config.max_changes:
        raise ValueError(f"change threshold exceeded: {len(changes)} > {config.max_changes}")
    return plan


def is_retryable_error(error: Exception) -> bool:
    """Retry only errors that carry a transient/network/throttling signal."""
    marker = getattr(error, "retryable", None)
    if marker is not None:
        return bool(marker)
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int):
        return status_code in {408, 429} or status_code >= 500
    return isinstance(error, (TimeoutError, ConnectionError))


def call_with_retry(
    operation: Callable[[], Any],
    *,
    attempts: int = 3,
    base_delay: float = 0.1,
    retry_if: Callable[[Exception], bool] | None = None,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            return operation()
        except Exception as exc:  # noqa: BLE001 - classification below is explicit
            last_error = exc
            retryable = retry_if(exc) if retry_if else is_retryable_error(exc)
            if attempt >= attempts or not retryable:
                break
            time.sleep(base_delay * (2 ** (attempt - 1)))
    raise last_error or RuntimeError("operation failed")


def apply_plan(
    plan: Sequence[PlanItem],
    *,
    dry_run: bool = True,
    allow_mutations: bool = False,
    max_changes: int = 100,
    create: Callable[[Mapping[str, Any]], Any] | None = None,
    update: Callable[[str, Mapping[str, Any]], Any] | None = None,
    journal: MutationJournal | None = None,
) -> list[dict[str, Any]]:
    """Apply through caller-provided adapters only after two explicit gates."""
    if max_changes < 0:
        raise ValueError("max_changes must be non-negative")
    changes = [item for item in plan if item.action != "unchanged"]
    if len(changes) > max_changes:
        raise ValueError(f"change threshold exceeded at mutation boundary: {len(changes)} > {max_changes}")
    invalid = [item.action for item in plan if item.action not in {"create", "update", "unchanged"}]
    if invalid:
        raise ValueError(f"unsupported plan action: {invalid[0]}")
    if dry_run or not allow_mutations:
        result = [{"action": item.action, "key": item.source.key, "applied": False, "reason": "dry_run_or_gate"} for item in plan]
        if journal:
            for entry in result:
                journal.record(**entry)
        return result
    if not create or not update:
        raise MutationNotAllowed("create and update adapters are required when mutations are enabled")
    applied: list[dict[str, Any]] = []
    for item in plan:
        try:
            if item.action == "create":
                create(item.payload)
            elif item.action == "update" and item.target_key:
                update(item.target_key, item.payload)
        except Exception as exc:  # noqa: BLE001 - expose the applied journal to the caller
            raise PartialMutationError(
                f"mutation failed for {item.action}:{item.source.key}; prior mutations may have been applied",
                applied,
            ) from exc
        entry = {"action": item.action, "key": item.source.key, "target_key": item.target_key, "applied": item.action != "unchanged"}
        applied.append(entry)
        if journal:
            journal.record(**entry)
    return applied
