import { appendFile, mkdir, readFile, rename, unlink, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { join } from "node:path";
import type { AgentEvent } from "../types.js";

export class DurableQueue {
  private readonly eventsPath: string;
  private readonly statePath: string;

  public constructor(private readonly directory: string) {
    this.eventsPath = join(directory, "events.jsonl");
    this.statePath = join(directory, "acknowledged.offset");
  }

  public async enqueue(events: readonly AgentEvent[]): Promise<void> {
    await mkdir(this.directory, { recursive: true });
    if (events.length) await appendFile(this.eventsPath, events.map((event) => JSON.stringify(event)).join("\n") + "\n", "utf8");
  }

  public async readUnacknowledged(): Promise<AgentEvent[]> {
    const events = await this.readEvents();
    const offset = await this.readOffset();
    if (offset > events.length) throw new Error("queue acknowledgement offset is beyond stored events");
    return events.slice(offset);
  }

  public async acknowledge(count: number): Promise<void> {
    if (!Number.isInteger(count) || count < 0) throw new RangeError("acknowledgement count must be a non-negative integer");
    const events = await this.readEvents();
    const current = await this.readOffset();
    if (current > events.length) throw new Error("queue acknowledgement offset is beyond stored events");
    if (count > events.length - current) throw new RangeError("cannot acknowledge more events than are available");
    await mkdir(this.directory, { recursive: true });
    const temporaryPath = `${this.statePath}.${randomUUID()}.tmp`;
    try {
      await writeFile(temporaryPath, String(current + count), "utf8");
      await rename(temporaryPath, this.statePath);
    } finally {
      try { await unlink(temporaryPath); } catch { /* the atomic rename already removed it */ }
    }
  }

  private async readEvents(): Promise<AgentEvent[]> {
    let text: string;
    try {
      text = await readFile(this.eventsPath, "utf8");
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
      throw new Error("queue event storage could not be read", { cause: error });
    }
    try {
      return text.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line) as AgentEvent);
    } catch (error) {
      throw new Error("queue event storage contains invalid JSONL", { cause: error });
    }
  }

  private async readOffset(): Promise<number> {
    let value: string;
    try {
      value = (await readFile(this.statePath, "utf8")).trim();
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return 0;
      throw new Error("queue acknowledgement state could not be read", { cause: error });
    }
    if (!/^\d+$/.test(value)) throw new Error("queue acknowledgement state is invalid");
    return Number(value);
  }
}
