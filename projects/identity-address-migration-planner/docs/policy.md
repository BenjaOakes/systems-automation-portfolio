# Defining migration policy

The planner does not know an organization's brands, departments, accepted suffixes, or alias-retention policy. Supply those decisions in a policy file and review them with the identity and messaging owners before generating a change plan.

Department rules take precedence over brand rules in the included example. Unknown values are blocked rather than silently routed to a default. The planner preserves current UPN, primary SMTP, and aliases as a semicolon-safe review field; a live implementation must still check the complete directory and Exchange address space immediately before mutation.

`ReviewRequired` is used when the supplied record contains conflicting current primary addresses. `Blocked` means the proposed value is invalid, collides, or relies on unknown policy. Neither status is executable.
