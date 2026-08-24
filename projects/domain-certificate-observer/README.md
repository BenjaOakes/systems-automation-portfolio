# Domain Certificate Observer

Operational posture: `FULL TOOL / READ-ONLY`. Fixture mode is network-free; live DNS/TLS checks and WHOIS are explicit opt-ins.

## Problem and use case

This standalone utility checks a domain inventory for DNS resolution, TLS certificate expiry/issuer changes, and optional WHOIS availability. It is aimed at systems engineers, platform teams, and security operations building a bounded scheduled probe.

## Architecture

`DomainObserver` orchestrates injected resolver, TLS, and WHOIS functions. TTL caching, serialized WHOIS rate limiting, and bounded workers keep network behavior explicit. Results are structured per domain, and the notification boundary is a caller-supplied function; the tool never posts to a webhook or sends mail implicitly.

## Installation and configuration

Python 3.10+ and the standard library are sufficient. From this project directory, set `PYTHONPATH=src` and run `python -m unittest discover -s tests -v`. `config/config.example.json` shows `domains`, expiry thresholds, `timeout_seconds`, `max_workers`, cache TTL, WHOIS interval, and server settings. The YAML file is an equivalent documentation template; the dependency-free CLI reads JSON.

## Usage and output

The offline example is `python -m domain_observer.cli --fixture examples/domains.fixture.json --json`. Live use accepts operator-supplied `--domain` values or JSON configuration; WHOIS requires `--whois`. The fixture contains an intentional expired result, so its monitoring exit code is `1`. Exit `0` means healthy; exit `1` means a finding or probe error; invalid input/configuration is argparse exit `2`. `--json` emits structured results, and `--csv path` writes a flat report.

## Permissions, safety, and limitations

Live mode needs outbound DNS and TCP/443; WHOIS additionally needs TCP/43 and may be rate-limited. `timeout_seconds` bounds the caller wait, though a timed-out daemon resolver may finish later. `whois_interval_seconds` serializes WHOIS calls. No credentials are required. WHOIS is best-effort metadata, not proof of ownership, and the tool does not prove application availability. Keep internal domains and notification configuration out of fixtures. Approved callers may pass a sink to `notify_results`; notification credentials remain external.

## Testing

Tests use fake probes and never open sockets or contact a registry. See [docs/configuration.md](docs/configuration.md).
