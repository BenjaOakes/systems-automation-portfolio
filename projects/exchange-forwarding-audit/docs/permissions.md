# Permissions and provider boundary

The public implementation consumes fixture data only. A production adapter would need to be designed and reviewed separately. It should request the minimum read-only permissions required to read mailbox forwarding state and the relevant audit sources, document retention windows, avoid logging access tokens or raw audit payloads, and preserve the report's redaction policy.

Authentication details are intentionally not embedded in this repository.
