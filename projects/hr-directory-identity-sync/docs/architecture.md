# Architecture

The project has four boundaries:

1. HR ingestion normalizes provider-shaped rows into `EmployeeRecord` values.
2. Directory providers return `DirectoryRecord` values and an explicit completeness flag.
3. The policy layer calculates desired identity attributes and group memberships from configuration.
4. The reconciliation engine matches, plans, and optionally applies changes through providers.

AD and Entra records with the same employee ID are merged into one hybrid identity for planning. Email-only matches are not silently selected when multiple records exist. The engine therefore remains useful for cloud-only, AD-only, or hybrid deployments without embedding a specific topology.
