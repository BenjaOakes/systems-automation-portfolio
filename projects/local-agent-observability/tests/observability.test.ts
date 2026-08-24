import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { test } from "node:test";
import { parseConfig } from "../src/config.js";
import { parseJsonl } from "../src/parsers/jsonl.js";
import { redactEvent, redactText, safeSessionIdentifier } from "../src/privacy/redact.js";
import { DurableQueue } from "../src/queue/durable-queue.js";
import { aggregateSessions } from "../src/sessions/aggregate.js";

test("config is explicitly no-network", () => {
  assert.throws(() => parseConfig({ inputFiles: [], stateDirectory: "state", outputFile: "report", noNetwork: false }));
});

test("parser reports malformed lines at a boundary", () => {
  const parsed = parseJsonl('{"sessionId":"one","timestamp":"2030-01-01T00:00:00Z","role":"user","content":"hello"}\nnot-json', "fixture");
  assert.equal(parsed.events.length, 1);
  assert.equal(parsed.issues[0].line, 2);
});

test("redaction removes common sensitive shapes", () => {
  const credentialName = ["api", "key"].join("_");
  const bearer = ["Bearer", "fixturetoken12345"].join(" ");
  const separator = String.fromCharCode(92);
  const localPath = ["C:", "sandbox", "fixture.txt"].join(separator);
  const uncPath = [separator, separator, "synthetic-host", "share", "fixture.txt"].join(separator);
  const text = redactText(`${bearer} ${credentialName}=fixture-value email=person@brand-a.example ${localPath} ${uncPath}`);
  assert.equal(text.includes("fixturetoken12345"), false);
  assert.equal(text.includes("person@brand-a.example"), false);
  assert.equal(text.includes(localPath), false);
  assert.equal(text.includes(uncPath), false);
});

test("session identifiers can be made stable without exposing the source key", () => {
  assert.equal(safeSessionIdentifier("fixture-session-001"), safeSessionIdentifier("fixture-session-001"));
  assert.notEqual(safeSessionIdentifier("fixture-session-001"), "fixture-session-001");
});

test("source paths never cross the public event or issue boundary", async () => {
  const separator = String.fromCharCode(92);
  const sensitiveSource = ["C:", "Users", "SyntheticUser", "PrivateProject", "session.jsonl"].join(separator);
  const parsed = parseJsonl('{"sessionId":"one","timestamp":"2030-01-01T00:00:00Z","role":"user","content":"hello"}\nnot-json', sensitiveSource);
  assert.equal(JSON.stringify(parsed).includes(sensitiveSource), false);
  const event = redactEvent({ ...parsed.events[0], source: sensitiveSource });
  assert.equal(JSON.stringify(event).includes(sensitiveSource), false);

  const directory = await mkdtemp(join(process.cwd(), ".test-state-private-"));
  try {
    const queue = new DurableQueue(directory);
    await queue.enqueue([event]);
    const persisted = await readFile(join(directory, "events.jsonl"), "utf8");
    assert.equal(persisted.includes(sensitiveSource), false);
    assert.equal(JSON.stringify(await queue.readUnacknowledged()).includes(sensitiveSource), false);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("aggregation and queue acknowledgement are durable", async () => {
  const directory = await mkdtemp(join(process.cwd(), ".test-state-"));
  try {
    const events = parseJsonl('{"sessionId":"one","timestamp":"2030-01-01T00:00:00Z","role":"user","content":"hello"}').events;
    assert.equal(aggregateSessions(events)[0].eventCount, 1);
    const queue = new DurableQueue(directory);
    await queue.enqueue(events);
    assert.equal((await queue.readUnacknowledged()).length, 1);
    await queue.acknowledge(1);
    assert.equal((await queue.readUnacknowledged()).length, 0);
    await readFile(join(directory, "acknowledged.offset"), "utf8");
    await assert.rejects(() => queue.acknowledge(-1), RangeError);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("queue storage failures are not converted to empty queues", async () => {
  const directory = await mkdtemp(join(process.cwd(), ".test-state-storage-"));
  try {
    await mkdir(join(directory, "events.jsonl"));
    await assert.rejects(() => new DurableQueue(directory).readUnacknowledged(), /storage could not be read/);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
