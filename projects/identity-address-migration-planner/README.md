# Identity Address Migration Planner

Operational posture: `PLANNING-ONLY`. This is an offline change-plan generator; no AD, Graph, Exchange, authentication, or mutation provider is included.

## Problem and use case

Changing a login address or primary email is easy to describe and hard to plan safely. Name normalization, brand and department policy, duplicate proposals, existing collisions, invalid addresses, review exceptions, and legacy alias preservation all need to be visible before an implementation adapter is considered.

This project models the planning side of larger UPN and primary-email migrations I have worked on. It focuses on deterministic proposals and reviewable exceptions, not on modifying a live directory or messaging system.

The intended audience is identity engineers, migration planners, directory administrators, and reviewers who need a deterministic proposal from synthetic or pre-approved input.

## Inputs and policy

The input JSON contains a `users` array. Each user has `GivenName`, `Surname`, `Department`, `Brand`, `CurrentUPN`, `CurrentPrimaryEmail`, and `ExistingAliases` (an array or semicolon-separated string). The policy contains `brand_domains` and `default_brand` plus optional `department_domains` overrides.

The planner lowercases and normalizes names into a local part, calculates both proposed UPN and primary email, validates the address shape, and preserves current UPN/email/aliases as a reviewable alias set. It checks proposed addresses against all supplied existing addresses, duplicate proposals, duplicate existing aliases, and conflicting current addresses.

Rows use `Ready`, `NoChange`, `ReviewRequired`, or `Blocked`. Unknown policy inputs, invalid addresses, duplicate identities, collisions, and ambiguous source data are not silently resolved. The generated plan is a proposal, not approval for a change.

## Installation and runnable example

Python 3.10+ and the standard library are sufficient:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
python -m identity_planner.cli --input examples/users.fixture.json --policy examples/policy.json --json
python -m identity_planner.cli --input examples/users.fixture.json --policy examples/policy.json --csv .\output\migration-plan.csv
```

The synthetic example is network-free and returns exit `0` because its rows are valid or unchanged. A plan containing blocked rows returns exit `1`; invalid CLI input returns argparse’s exit `2`.

## Architecture, safety, and limitations

Records are loaded into pure planning calculations and serialized as JSON or CSV. There is no live directory lookup, so a real migration would still need a complete directory-wide collision check, approval workflow, and a separately reviewed mutation adapter. Do not put real identities, internal domains, credentials, or production exports in fixtures. See [docs/policy.md](docs/policy.md) for policy semantics.

## Testing

Tests cover normalization, domain policy, alias parsing/preservation, duplicate proposals, existing-address collisions, invalid input, and the explicit no-provider boundary.
