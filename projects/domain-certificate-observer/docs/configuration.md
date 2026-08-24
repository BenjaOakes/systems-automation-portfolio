# Configuration and network posture

The runnable CLI reads JSON so the project remains dependency-free. `config.example.yaml` is an equivalent human-readable template for teams that already standardize on YAML; convert it to JSON or load it through an organization-owned configuration layer.

Live mode performs outbound DNS and TLS/443 checks. WHOIS is disabled unless `--whois` is supplied, because registry services have different rate limits and response formats. The observer never sends credentials and does not prove certificate ownership or application health.

Use a conservative worker count and cache interval for scheduled checks. The injectable resolver, TLS probe, and WHOIS probe are the provider boundary for tests or an organization-specific notification/registry adapter. A notification adapter should receive the structured results after the scan; it should not be embedded in the probe loop.
