# Troubleshooting

`Blocked` items include machine-readable reasons. Start with `duplicate_hr_employee_id`, `ambiguous_directory_match`, `upn_or_mail_collision`, `missing_*`, or `unknown_*` policy reasons. A `ReviewRequired` item is intentionally not executable; resolve the source-data issue and rerun the plan.

If a provider reports incomplete collection, fix pagination or retry handling rather than lowering the safety gate. If a second run still proposes changes after mock execution, inspect the provider's normalization and post-step verification contract.
