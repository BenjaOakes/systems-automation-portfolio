"""Command-line entry point with network-free fixture mode."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from .core import CertificateRecord, DomainObserver, DomainResult, ObserverConfig, check_expiry_status, exit_code, probe_whois


def _fixture_results(path: Path) -> list[DomainResult]:
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    results: list[DomainResult] = []
    for item in payload.get("domains", []):
        certificate = item.get("certificate")
        record = None
        if certificate:
            from datetime import datetime

            record = CertificateRecord(
                datetime.fromisoformat(certificate["expires_at"].replace("Z", "+00:00"))
                if certificate.get("expires_at")
                else None,
                certificate.get("issuer"),
                certificate.get("subject"),
            )
        results.append(
            DomainResult(
                domain=item["domain"].lower().rstrip("."),
                dns_addresses=tuple(item.get("dns_addresses", [])),
                certificate=record,
                expiry_status=check_expiry_status(
                    record.expires_at if record else None,
                    warning_days=int(payload.get("expiry_warning_days", 30)),
                    critical_days=int(payload.get("expiry_critical_days", 7)),
                ),
                whois=item.get("whois"),
                errors=tuple(item.get("errors", [])),
            )
        )
    return sorted(results, key=lambda result: result.domain)


def _load_config(path: Path) -> dict[str, Any]:
    """Load JSON configuration; YAML is supplied as documentation, not a runtime dependency."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("domains"), list):
        raise ValueError("configuration must contain a domains list")
    return value


def _write_csv(results: list[DomainResult], path: Path | None) -> None:
    rows = [result.as_dict() for result in results]
    handle = path.open("w", newline="", encoding="utf-8") if path else None
    try:
        output = handle or __import__("sys").stdout
        writer = csv.DictWriter(output, fieldnames=["domain", "expiry_status", "dns_addresses", "issuer", "expires_at", "errors"])
        writer.writeheader()
        for row in rows:
            certificate = row["certificate"] or {}
            writer.writerow({
                "domain": row["domain"],
                "expiry_status": row["expiry_status"],
                "dns_addresses": ";".join(row["dns_addresses"]),
                "issuer": certificate.get("issuer", ""),
                "expires_at": certificate.get("expires_at", ""),
                "errors": ";".join(row["errors"]),
            })
    finally:
        if handle:
            handle.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Observe DNS and TLS health for a domain inventory.")
    parser.add_argument("-d", "--domain", action="append", default=[], help="Domain to check in live mode.")
    parser.add_argument("--fixture", type=Path, help="Read synthetic results without network access.")
    parser.add_argument("--config", type=Path, help="Read a JSON configuration containing domains and thresholds.")
    parser.add_argument("--json", action="store_true", help="Emit JSON rather than a console table.")
    parser.add_argument("--csv", type=Path, help="Write a flat CSV report (live or fixture mode).")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--whois", action="store_true", help="Opt in to WHOIS port 43 queries.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.fixture:
        try:
            results = _fixture_results(args.fixture)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            parser.error(f"invalid fixture: {exc}")
    elif args.domain or args.config:
        config_data: dict[str, Any] = {}
        if args.config:
            try:
                config_data = _load_config(args.config)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                parser.error(f"invalid configuration: {exc}")
        domains = args.domain or [str(item) for item in config_data.get("domains", [])]
        if not domains:
            parser.error("configuration must contain at least one domain")
        timeout = float(config_data.get("timeout_seconds", args.timeout))
        workers = int(config_data.get("max_workers", args.workers))
        warning_days = int(config_data.get("expiration_warning_days", config_data.get("expiry_warning_days", 30)))
        critical_days = int(config_data.get("expiration_critical_days", config_data.get("expiry_critical_days", 7)))
        if args.workers < 1 or args.timeout <= 0:
            parser.error("--workers must be positive and --timeout must be greater than zero")
        if workers < 1 or timeout <= 0:
            parser.error("max_workers must be positive and timeout_seconds must be greater than zero")
        observer_config = ObserverConfig(
            max_workers=workers,
            timeout_seconds=timeout,
            expiry_warning_days=warning_days,
            expiry_critical_days=critical_days,
            cache_ttl_seconds=float(config_data.get("cache_ttl_seconds", 300)),
            whois_interval_seconds=float(config_data.get("whois_interval_seconds", 1)),
            whois_server=str(config_data.get("whois_server", "whois.iana.org")),
        )
        whois_probe = (lambda domain, probe_timeout: probe_whois(domain, probe_timeout, observer_config.whois_server)) if args.whois else None
        observer = DomainObserver(observer_config, whois_probe=whois_probe)
        results = observer.observe(domains)
    else:
        parser.error("provide --fixture or at least one --domain")
    if args.csv:
        _write_csv(results, args.csv)
    elif args.json:
        print(json.dumps([result.as_dict() for result in results], indent=2, sort_keys=True))
    else:
        for result in results:
            print(f"{result.domain:32} {result.expiry_status:8} {', '.join(result.dns_addresses) or '-'}")
            for error in result.errors:
                print(f"  error: {error}")
    return exit_code(results)


if __name__ == "__main__":
    raise SystemExit(main())
