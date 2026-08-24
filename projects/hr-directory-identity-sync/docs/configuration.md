# Configuration

The runnable CLI uses JSON and the repository includes equivalent YAML templates for teams that standardize on YAML. Authentication and directory connection settings are examples only; the mock workflow never reads credentials or connects to a provider.

Environment-specific values belong in an approved secret/configuration system: tenant and application identifiers, certificate references, AD search bases, HR endpoints, group IDs, and suffixes. Do not put client secrets, access tokens, private keys, or certificate contents in JSON/YAML. Use a certificate store, managed identity, SecretManagement, Windows Credential Manager, or a cloud vault according to the target environment.
