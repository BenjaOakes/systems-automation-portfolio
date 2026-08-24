import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { loadConfig, parseConfig } from "./config.js";
import { parseJsonl } from "./parsers/jsonl.js";
import { redactEvent, safeSourceIdentifier } from "./privacy/redact.js";
import { DurableQueue } from "./queue/durable-queue.js";
import { aggregateSessions } from "./sessions/aggregate.js";
import type { AgentEvent, ObserverConfig } from "./types.js";

export async function run(config: ObserverConfig) {
  const parsed = (await Promise.all(config.inputFiles.map(async (path) => parseJsonl(await readFile(path, "utf8"), path, { hashSessionIds: config.hashSessionIds }))));
  const issues = parsed.flatMap((item) => item.issues).map((issue) => ({ ...issue, source: safeSourceIdentifier(issue.source) }));
  const events: AgentEvent[] = parsed.flatMap((item) => item.events).map((event) => redactEvent(event, config.redactLocalPaths)).slice(0, config.maxEvents);
  const queue = new DurableQueue(config.stateDirectory);
  await queue.enqueue(events);
  const report = { network: "disabled", redaction: "enabled", eventCount: events.length, truncated: events.length >= config.maxEvents, issues, sessions: aggregateSessions(events) };
  await mkdir(dirname(config.outputFile), { recursive: true });
  await writeFile(config.outputFile, JSON.stringify(report, null, 2) + "\n", "utf8");
  return report;
}

function arg(name: string): string | undefined {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

if (process.argv[1]?.endsWith("index.ts") || process.argv[1]?.endsWith("index.js")) {
  const input = arg("--input");
  const configPath = arg("--config");
  const output = arg("--output") ?? "local-report.json";
  const config = configPath
    ? await loadConfig(configPath)
    : input
      ? parseConfig({ inputFiles: [input], stateDirectory: ".local-state", outputFile: output, noNetwork: true })
      : (() => { throw new Error("--input or --config is required"); })();
  await run(config);
  console.log(`wrote ${config.outputFile}`);
}
