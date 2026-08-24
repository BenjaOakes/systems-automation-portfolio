from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping


_DOMAIN_PATTERN = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


@dataclass(frozen=True)
class Policy:
    brand_domains: Mapping[str, str]
    default_brand: str
    department_domains: Mapping[str, str]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Policy":
        raw_brands = data.get("brand_domains")
        if not isinstance(raw_brands, Mapping) or not raw_brands:
            raise ValueError("brand_domains must be a non-empty mapping")
        domains = {str(key).casefold(): str(value).casefold().lstrip("@") for key, value in raw_brands.items()}
        if any(not valid_domain(value) for value in domains.values()):
            raise ValueError("brand_domains contains an invalid domain")
        raw_departments = data.get("department_domains", {})
        if not isinstance(raw_departments, Mapping):
            raise ValueError("department_domains must be a mapping")
        departments = {str(key).casefold(): str(value).casefold().lstrip("@") for key, value in raw_departments.items()}
        if any(not valid_domain(value) for value in departments.values()):
            raise ValueError("department_domains contains an invalid domain")
        default = str(data.get("default_brand", next(iter(domains)))).casefold()
        if default not in domains:
            raise ValueError(f"default brand is not configured: {default}")
        return cls(domains, default, departments)


def normalize_local_part(given_name: str, surname: str) -> str:
    value = re.sub(r"[^a-z0-9]+", ".", f"{given_name}.{surname}".casefold())
    value = re.sub(r"\.{2,}", ".", value).strip(".")
    return value


def normalize_address(value: str | None) -> str:
    return str(value or "").strip().casefold()


def valid_address(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+", value))


def valid_domain(value: str) -> bool:
    return bool(_DOMAIN_PATTERN.fullmatch(value.casefold().lstrip("@")))


class PolicyResolutionError(ValueError):
    """A record contains policy input that requires review before planning."""


def _domain_for(record: Mapping[str, Any], policy: Policy) -> str:
    brand = str(record.get("Brand", "")).casefold()
    department = str(record.get("Department", "")).casefold()
    if department:
        if department not in policy.department_domains:
            raise PolicyResolutionError(f"unknown_department:{department}")
        return policy.department_domains[department]
    if brand:
        if brand not in policy.brand_domains:
            raise PolicyResolutionError(f"unknown_brand:{brand}")
        return policy.brand_domains[brand]
    return policy.brand_domains[policy.default_brand]


def _aliases(record: Mapping[str, Any]) -> list[str]:
    aliases = record.get("ExistingAliases", []) or []
    if isinstance(aliases, str):
        aliases = [item.strip() for item in aliases.split(";") if item.strip()]
    candidates = [record.get("CurrentUPN"), record.get("CurrentPrimaryEmail"), *aliases]
    normalized: set[str] = set()
    for value in candidates:
        if value is None:
            continue
        candidate = re.sub(r"^smtp:", "", str(value).strip(), flags=re.IGNORECASE)
        if candidate:
            normalized.add(normalize_address(candidate))
    return sorted(normalized)


def plan_migration(records: Iterable[Mapping[str, Any]], policy: Policy) -> list[dict[str, Any]]:
    rows = list(records)
    proposals: list[dict[str, Any]] = []
    proposed_upns: dict[str, int] = {}
    proposed_emails: dict[str, int] = {}
    existing_addresses = {address for record in rows for address in _aliases(record)}
    existing_owners: dict[str, int] = {}
    for index, record in enumerate(rows):
        for address in _aliases(record):
            existing_owners[address] = existing_owners.get(address, 0) + 1
    for index, record in enumerate(rows):
        local_part = normalize_local_part(str(record.get("GivenName", "")), str(record.get("Surname", "")))
        reasons: list[str] = []
        try:
            domain = _domain_for(record, policy)
        except PolicyResolutionError as exc:
            domain = ""
            reasons.append(str(exc))
        proposed_upn = f"{local_part}@{domain}" if local_part and domain else ""
        proposed_email = proposed_upn
        if proposed_upn:
            proposed_upns[proposed_upn] = proposed_upns.get(proposed_upn, 0) + 1
        if proposed_email:
            proposed_emails[proposed_email] = proposed_emails.get(proposed_email, 0) + 1
        current_upn = normalize_address(record.get("CurrentUPN"))
        current_email = normalize_address(record.get("CurrentPrimaryEmail"))
        review_reasons: list[str] = []
        if current_upn and current_email and current_upn != current_email:
            # A planner must not silently choose which existing primary to retain;
            # the reviewer needs to resolve the source-of-truth discrepancy.
            review_reasons.append("multiple_current_addresses")
        if not local_part:
            reasons.append("empty_normalized_local_part")
        if not reasons and (not valid_address(proposed_upn) or not valid_address(proposed_email)):
            reasons.append("invalid_proposed_address")
        for address in (proposed_upn, proposed_email):
            if address and address in existing_addresses and address not in {current_upn, current_email}:
                reasons.append(f"existing_collision:{address}")
        unchanged = current_upn == proposed_upn and current_email == proposed_email
        status = "Blocked" if reasons else ("ReviewRequired" if review_reasons else ("NoChange" if unchanged else "Ready"))
        all_reasons = reasons + review_reasons
        proposals.append({
            "CurrentUPN": current_upn,
            "ProposedUPN": proposed_upn,
            "CurrentPrimaryEmail": current_email,
            "ProposedPrimaryEmail": proposed_email,
            "AliasesToPreserve": ";".join(_aliases(record)),
            "Status": status,
            "Reason": ";".join(all_reasons) if all_reasons else ("already_matches_policy" if unchanged else "policy_validated"),
            "InputIndex": index,
        })
    for row in proposals:
        if proposed_upns.get(row["ProposedUPN"], 0) > 1:
            row["Reason"] = ";".join(filter(None, [row["Reason"], "duplicate_proposal"]))
            row["Status"] = "Blocked"
        if proposed_emails.get(row["ProposedPrimaryEmail"], 0) > 1:
            row["Reason"] = ";".join(filter(None, [row["Reason"], "duplicate_email_proposal"]))
            row["Status"] = "Blocked"
    # Duplicate existing aliases are a source-data conflict even when the
    # proposed address itself is unique. Keeping this visible prevents an
    # implementation adapter from accidentally stealing an alias.
    for row, record in zip(proposals, rows):
        duplicated = sorted({address for address in _aliases(record) if existing_owners.get(address, 0) > 1})
        if duplicated:
            row["Status"] = "Blocked"
            row["Reason"] = ";".join(filter(None, [row["Reason"], "duplicate_existing_address:" + ",".join(duplicated)]))
        row.pop("InputIndex", None)
    return proposals
