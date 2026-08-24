from __future__ import annotations

import re
from typing import Any, Mapping

from ..models.records import EmployeeRecord


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def normalize_email(value: Any) -> str:
    return str(value or "").strip().casefold()


def normalize_employee(raw: Mapping[str, Any], row_number: int = 0) -> EmployeeRecord:
    """Normalize provider-shaped HR fields once at the ingestion boundary.

    Keeping the original row number makes invalid records reviewable without
    copying the source payload into an audit report.
    """
    employee_id = str(raw.get("employee_id", raw.get("EmployeeId", ""))).strip()
    given_name = str(raw.get("given_name", raw.get("GivenName", ""))).strip()
    surname = str(raw.get("surname", raw.get("Surname", ""))).strip()
    email = normalize_email(raw.get("work_email", raw.get("WorkEmail", raw.get("email", ""))))
    department = str(raw.get("department", raw.get("Department", ""))).strip()
    brand = str(raw.get("brand", raw.get("Brand", ""))).strip()
    employee_type = str(raw.get("employee_type", raw.get("EmployeeType", "employee"))).strip()
    status = normalize_text(raw.get("status", raw.get("Status", "active")))
    manager = str(raw.get("manager_employee_id", raw.get("ManagerEmployeeId", ""))).strip() or None
    errors: list[str] = []
    if not employee_id:
        errors.append("missing_employee_id")
    if not given_name or not surname:
        errors.append("missing_name")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errors.append("invalid_work_email")
    if not department:
        errors.append("missing_department")
    if not brand:
        errors.append("missing_brand")
    if status not in {"active", "leave", "terminated", "inactive"}:
        errors.append(f"invalid_status:{status}")
    return EmployeeRecord(employee_id, given_name, surname, email, department, brand, employee_type, status, manager, row_number, tuple(errors))
