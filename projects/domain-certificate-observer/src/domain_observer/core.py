"""Provider-neutral domain monitoring with injectable network boundaries."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timezone
from queue import Queue
import socket
import ssl
import re
import threading
import time
from typing import Any, Callable, Iterable, Mapping, Sequence


_DOMAIN_PATTERN = re.compile(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", re.IGNORECASE)


@dataclass(frozen=True)
class ObserverConfig:
    timeout_seconds: float = 5.0
    expiry_warning_days: int = 30
    expiry_critical_days: int = 7
    max_workers: int = 4
    whois_interval_seconds: float = 0.0
    cache_ttl_seconds: float = 300.0
    whois_server: str = "whois.iana.org"

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if self.expiry_warning_days < 0 or self.expiry_critical_days < 0:
            raise ValueError("expiry thresholds must be non-negative")
        if self.expiry_critical_days > self.expiry_warning_days:
            raise ValueError("expiry_critical_days cannot exceed expiry_warning_days")
        if self.max_workers < 1:
            raise ValueError("max_workers must be positive")
        if self.whois_interval_seconds < 0 or self.cache_ttl_seconds < 0:
            raise ValueError("rate and cache intervals must be non-negative")


def normalize_domain(value: str) -> str:
    """Normalize a DNS name without attempting to infer a private suffix."""
    return str(value or "").strip().casefold().rstrip(".")


def valid_domain(value: str) -> bool:
    """Accept public-looking DNS names while rejecting whitespace and labels over DNS limits."""
    return bool(_DOMAIN_PATTERN.fullmatch(normalize_domain(value)))


@dataclass(frozen=True)
class CertificateRecord:
    expires_at: datetime | None
    issuer: str | None = None
    subject: str | None = None


@dataclass(frozen=True)
class DomainResult:
    domain: str
    dns_addresses: tuple[str, ...] = ()
    certificate: CertificateRecord | None = None
    expiry_status: str = "unknown"
    whois: Mapping[str, Any] | None = None
    errors: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        certificate = None
        if self.certificate:
            certificate = {
                "expires_at": self.certificate.expires_at.isoformat()
                if self.certificate.expires_at
                else None,
                "issuer": self.certificate.issuer,
                "subject": self.certificate.subject,
            }
        return {
            "domain": self.domain,
            "dns_addresses": list(self.dns_addresses),
            "certificate": certificate,
            "expiry_status": self.expiry_status,
            "whois": dict(self.whois) if self.whois else None,
            "errors": list(self.errors),
        }


def _utc(value: datetime | date | str) -> datetime:
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = value
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def check_expiry_status(
    expires_at: datetime | date | str | None,
    *,
    now: datetime | None = None,
    warning_days: int = 30,
    critical_days: int = 7,
) -> str:
    """Return a stable monitoring state for a certificate expiry timestamp."""
    if expires_at is None:
        return "unknown"
    remaining = (_utc(expires_at) - _utc(now or datetime.now(timezone.utc))).total_seconds() / 86400
    if remaining < 0:
        return "expired"
    if remaining <= critical_days:
        return "critical"
    if remaining <= warning_days:
        return "warning"
    return "healthy"


class TTLCache:
    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = max(0.0, ttl_seconds)
        self._values: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any:
        with self._lock:
            entry = self._values.get(key)
            if not entry:
                return None
            if self._ttl <= 0 or time.monotonic() - entry[0] > self._ttl:
                self._values.pop(key, None)
                return None
            return entry[1]

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._values[key] = (time.monotonic(), value)


class RateLimiter:
    """A small serialized limiter suitable for registry/WHOIS calls."""

    def __init__(self, interval_seconds: float) -> None:
        self._interval = max(0.0, interval_seconds)
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next - now)
            self._next = max(now, self._next) + self._interval
        if delay:
            time.sleep(delay)


Resolver = Callable[[str, float], Iterable[str]]
CertificateProbe = Callable[[str, float], CertificateRecord]
WhoisProbe = Callable[[str, float], Mapping[str, Any]]
NotificationSink = Callable[[Sequence[DomainResult]], None]


def notify_results(results: Sequence[DomainResult], sink: NotificationSink | None = None) -> None:
    """Deliver structured results to an explicitly supplied local consumer.

    The observer never posts to a webhook or sends email implicitly. A caller
    can adapt this boundary to its approved notification system after review.
    """
    if sink:
        sink(tuple(results))


def resolve_dns(domain: str, timeout: float) -> Iterable[str]:
    """Resolve a domain with a bounded caller wait.

    ``getaddrinfo`` does not accept a per-call timeout.  A daemon worker keeps
    a slow resolver from blocking the observer indefinitely while avoiding a
    process-wide ``socket.setdefaulttimeout`` mutation.
    """
    results: Queue[tuple[list[str] | None, BaseException | None]] = Queue(maxsize=1)

    def resolve() -> None:
        try:
            addresses = sorted({item[4][0] for item in socket.getaddrinfo(domain, 443, type=socket.SOCK_STREAM)})
            results.put((addresses, None))
        except BaseException as exc:  # noqa: BLE001 - preserve resolver failure for the caller
            results.put((None, exc))

    worker = threading.Thread(target=resolve, name=f"dns:{domain}", daemon=True)
    worker.start()
    worker.join(timeout=max(0.0, timeout))
    if worker.is_alive():
        raise TimeoutError(f"DNS resolution timed out after {timeout} seconds")
    addresses, error = results.get_nowait()
    if error is not None:
        raise error
    return addresses or []


def probe_tls(domain: str, timeout: float) -> CertificateRecord:
    context = ssl.create_default_context()
    with socket.create_connection((domain, 443), timeout=timeout) as raw:
        with context.wrap_socket(raw, server_hostname=domain) as connection:
            certificate = connection.getpeercert()
            expires = certificate.get("notAfter")
            expiry = datetime.strptime(expires, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc) if expires else None
            issuer = ", ".join("=".join(part) for group in certificate.get("issuer", ()) for part in group)
            subject = ", ".join("=".join(part) for group in certificate.get("subject", ()) for part in group)
            return CertificateRecord(expires, issuer or None, subject or None)


def probe_whois(domain: str, timeout: float, server: str = "whois.iana.org") -> Mapping[str, Any]:
    """Perform an explicitly requested, best-effort WHOIS query.

    WHOIS is deliberately an adapter rather than a required part of a health
    check: registries differ in response format and rate limits. The caller
    must opt in, and the observer still reports the raw availability result
    as data rather than treating it as proof of ownership.
    """
    with socket.create_connection((server, 43), timeout=timeout) as connection:
        connection.sendall((f"{domain}\r\n").encode("ascii"))
        chunks: list[bytes] = []
        while True:
            chunk = connection.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    text = b"".join(chunks).decode("utf-8", errors="replace")
    fields: dict[str, Any] = {"server": server, "response_available": bool(text.strip())}
    for line in text.splitlines():
        if ":" not in line or line.lstrip().startswith("%"):
            continue
        name, value = line.split(":", 1)
        name = name.strip().casefold().replace(" ", "_")
        value = value.strip()
        if name and value and name not in fields:
            fields[name] = value
    return fields


class DomainObserver:
    def __init__(
        self,
        config: ObserverConfig | None = None,
        *,
        resolver: Resolver = resolve_dns,
        certificate_probe: CertificateProbe = probe_tls,
        whois_probe: WhoisProbe | None = None,
    ) -> None:
        self.config = config or ObserverConfig()
        self.resolver = resolver
        self.certificate_probe = certificate_probe
        self.whois_probe = whois_probe
        self._cache = TTLCache(self.config.cache_ttl_seconds)
        self._whois_limiter = RateLimiter(self.config.whois_interval_seconds)

    def observe_domain(self, domain: str) -> DomainResult:
        normalized = normalize_domain(domain)
        if not valid_domain(normalized):
            return DomainResult(normalized, errors=("invalid_domain",))
        errors: list[str] = []
        addresses: tuple[str, ...] = ()
        certificate: CertificateRecord | None = None
        try:
            cached = self._cache.get(f"dns:{normalized}")
            addresses = tuple(cached) if cached is not None else tuple(sorted(set(self.resolver(normalized, self.config.timeout_seconds))))
            if cached is None:
                self._cache.put(f"dns:{normalized}", addresses)
        except Exception as exc:  # noqa: BLE001 - monitoring must report per-domain failure
            errors.append(f"dns:{type(exc).__name__}")
        try:
            cached = self._cache.get(f"tls:{normalized}")
            certificate = cached or self.certificate_probe(normalized, self.config.timeout_seconds)
            self._cache.put(f"tls:{normalized}", certificate)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"tls:{type(exc).__name__}")
        whois: Mapping[str, Any] | None = None
        if self.whois_probe:
            try:
                self._whois_limiter.wait()
                whois = self.whois_probe(normalized, self.config.timeout_seconds)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"whois:{type(exc).__name__}")
        state = check_expiry_status(
            certificate.expires_at if certificate else None,
            warning_days=self.config.expiry_warning_days,
            critical_days=self.config.expiry_critical_days,
        )
        return DomainResult(normalized, addresses, certificate, state, whois, tuple(errors))

    def observe(self, domains: Iterable[str]) -> list[DomainResult]:
        unique = sorted({normalize_domain(domain) for domain in domains if str(domain).strip()})
        with ThreadPoolExecutor(max_workers=max(1, self.config.max_workers)) as executor:
            futures = {executor.submit(self.observe_domain, domain): domain for domain in unique}
            results = [future.result() for future in as_completed(futures)]
        return sorted(results, key=lambda result: result.domain)


def exit_code(results: Iterable[DomainResult]) -> int:
    return 1 if any(result.errors or result.expiry_status in {"expired", "critical", "warning"} for result in results) else 0
