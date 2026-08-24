# Identity matching

Matching is deterministic and ordered:

- an exact HR employee ID match wins;
- otherwise, the normalized work email is compared to UPN, mail, and aliases;
- zero candidates creates a new-identity proposal;
- multiple candidates produce `Blocked` with `ambiguous_directory_match`;
- duplicate HR IDs, invalid inputs, unknown policy values, and UPN/mail collisions are blocked.

Matching never uses display name alone. A manager reference is resolved against the complete HR employee-ID set. A missing manager is `ReviewRequired`, because the identity can be planned but the relationship cannot be safely asserted.
