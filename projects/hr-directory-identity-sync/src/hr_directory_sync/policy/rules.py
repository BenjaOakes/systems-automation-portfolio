from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from ..models.records import EmployeeRecord


class PolicyError(ValueError):
    """A policy input is missing or cannot safely produce an identity."""


def _domain(value: Any) -> str:
    result = str(value or "").strip().casefold().lstrip("@")
    if not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,62}", result):
        raise PolicyError(f"invalid_domain:{result}")
    return result


@dataclass(frozen=True)
class Policy:
    brand_domains: Mapping[str, str]
    default_brand: str
    department_to_groups: Mapping[str, tuple[str, ...]]
    managed_attributes: tuple[str, ...]
    employee_type_rules: Mapping[str, Mapping[str, Any]]

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Policy":
        raw_brands = data.get("brand_domains", data.get("brand_mappings", {}))
        if not isinstance(raw_brands, Mapping) or not raw_brands:
            raise PolicyError("brand_domains must be a non-empty mapping")
        brands = {str(key).casefold(): _domain(value) for key, value in raw_brands.items()}
        default = str(data.get("default_brand", next(iter(brands)))).casefold()
        if default not in brands:
            raise PolicyError(f"unknown_default_brand:{default}")
        raw_groups = data.get("department_to_groups", data.get("group_mappings", {}))
        if not isinstance(raw_groups, Mapping):
            raise PolicyError("department_to_groups must be a mapping")
        groups = {str(key).casefold(): tuple(str(item) for item in value) for key, value in raw_groups.items()}
        managed = tuple(str(item) for item in data.get("managed_attributes", ["display_name", "department", "brand", "employee_type", "manager_employee_id", "user_principal_name", "mail", "enabled", "groups"]))
        raw_types = data.get("employee_type_rules", {})
        if not isinstance(raw_types, Mapping):
            raise PolicyError("employee_type_rules must be a mapping")
        return cls(brands, default, groups, managed, {str(k).casefold(): dict(v) for k, v in raw_types.items()})

    def desired_attributes(self, employee: EmployeeRecord) -> dict[str, Any]:
        brand = employee.brand.casefold()
        department = employee.department.casefold()
        if brand not in self.brand_domains:
            raise PolicyError(f"unknown_brand:{brand}")
        if department not in self.department_to_groups:
            raise PolicyError(f"unknown_department:{department}")
        local = re.sub(r"[^a-z0-9]+", ".", f"{employee.given_name}.{employee.surname}".casefold()).strip(".")
        if not local:
            raise PolicyError("empty_normalized_local_part")
        rule = self.employee_type_rules.get(employee.employee_type.casefold(), {})
        enabled = employee.status not in {"terminated", "inactive"} and bool(rule.get("enabled", True))
        domain = self.brand_domains[brand]
        upn = f"{local}@{domain}"
        return {
            "employee_id": employee.employee_id,
            "display_name": f"{employee.given_name} {employee.surname}",
            "given_name": employee.given_name,
            "surname": employee.surname,
            "department": employee.department,
            "brand": employee.brand,
            "employee_type": employee.employee_type,
            "user_principal_name": upn,
            "mail": upn,
            "enabled": enabled,
            "manager_employee_id": employee.manager_employee_id,
            "groups": list(self.department_to_groups[department]),
        }
