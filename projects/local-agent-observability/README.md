# Local Agent Observability

Operational posture: `FULL TOOL / READ-ONLY / LOCAL-ONLY`. The default configuration requires no network, and no uploader or dashboard is included.

## Problem and use case

Local developer-agent session files can contain prompts, source fragments, commands, URLs, tokens, and personal data. Useful observability therefore starts with a narrow parser contract and a privacy boundary before aggregation or retention.

This project reflects experience building local developer/AI tooling: TypeScript parsing, privacy-aware redaction, source-path protection, aggregation, durable queues, and local-only processing without an uploader.

The intended audience is developer-experience engineers, platform teams, systems engineers, privacy-conscious tooling authors, and TypeScript developers interested in local telemetry.

## Architecture

The tool reads only the caller-selected JSONL input paths. `parseJsonl` normalizes a documented event shape and immediately replaces source paths with deterministic non-reversible identifiers; parser issues use the same safe representation. `redactEvent` removes email-like values, bearer/API-token shapes, and local/UNC paths from content. `aggregateSessions` produces summaries, while `DurableQueue` stores redacted events and an atomically updated acknowledgement offset under the configured state directory.

## Installation and configuration

Node.js 20+ and npm are expected:

```powershell
npm ci
npm test
npm run build
```

`examples/config.example.json` shows `inputFiles`, `stateDirectory`, `outputFile`, `noNetwork`, `redactLocalPaths`, `hashSessionIds`, and `maxEvents`. Paths are caller-owned local paths. `noNetwork: true` is mandatory; changing it is rejected by configuration parsing.

```powershell
npm run dev -- --input examples/session.fixture.jsonl --output .\output\local-report.json
npm run dev -- --config examples/config.example.json
```

The report contains network/redaction flags, event count, parse issues, and session summaries. Queue state is local runtime state and must never be committed.

## Privacy and safety

The tool reads the selected files and writes only the selected report plus queue state. Source paths are protected before they enter issue output or queue data; session IDs can be hashed; raw content is not written to the report. Redaction is defense in depth, not a proof of safety for arbitrary text. Do not point it at production transcripts or personal logs without a separate privacy review, retention decision, and source-path permission review. There is no network call in the implementation.

## Testing and limitations

`node:test` cases cover configuration validation, malformed JSONL, redaction, source-path protection, aggregation, queue acknowledgement, and storage failures. The parser intentionally supports a small documented schema rather than guessing at vendor-private formats. See the source types and fixture for the input contract.
