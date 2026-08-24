# Safety model

Preview is the default. `-Execute` is required for mutation and PowerShell `-WhatIf` remains effective. Protected identities are rejected before provider operations begin. Failed phases persist a failure record and stop; retries are limited to classified transient failures. State files are identity-bound and schema-checked.

The included provider is entirely in-memory. Do not connect a real provider until the workflow phases, protected identity list, permissions, state retention, alerting, and recovery plan have been independently approved.
