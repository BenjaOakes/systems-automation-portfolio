# Publication safety

The projects here are intentionally built at a public-safe boundary. The public tree contains only generic implementations, synthetic examples, and explicit provider/configuration seams.

The public-facing code uses fictional identities, `.example` domains, synthetic records, mock providers, and fixture-first commands. It does not contain live connector defaults, tenant identifiers, application identifiers, group identifiers, credentials, certificates, transcripts, reports, logs, state, or production policy.

Preparation reports, generated scans, runtime state, logs, and local build output are not publication content. Exclude them from any public export and run the scanner against the exact tree intended for publication, not just the source-controlled subset.

`REVIEW REQUIRED` remains the correct outcome whenever ownership, licensing, provider permissions, privacy, or an indicator found by the scanner has not been independently cleared.
