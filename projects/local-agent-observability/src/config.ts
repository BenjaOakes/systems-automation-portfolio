import { readFile } from "node:fs/promises";
import type { ObserverConfig } from "./types.js";

export function parseConfig(value: unknown): ObserverConfig {
  if (!value || typeof value !== "object") throw new Error("configuration must be an object");
  const candidate = value as Record<string, unknown>;
  const inputFiles = candidate.inputFiles;
  if (!Array.isArray(inputFiles) || inputFiles.some((item) => typeof item !== "string")) {
    throw new Error("inputFiles must be an array of paths");
  }
  if (candidate.noNetwork !== true) throw new Error("noNetwork must be true for the public implementation");
  const stateDirectory = candidate.stateDirectory;
  const outputFile = candidate.outputFile;
  if (typeof stateDirectory !== "string" || typeof outputFile !== "string") {
    throw new Error("stateDirectory and outputFile are required strings");
  }
  const maxEvents = candidate.maxEvents === undefined ? 100000 : candidate.maxEvents;
  if (typeof maxEvents !== "number" || !Number.isInteger(maxEvents) || maxEvents < 1) {
    throw new Error("maxEvents must be a positive integer");
  }
  return {
    inputFiles,
    stateDirectory,
    outputFile,
    noNetwork: true,
    redactLocalPaths: candidate.redactLocalPaths !== false,
    hashSessionIds: candidate.hashSessionIds !== false,
    maxEvents,
  };
}

export async function loadConfig(path: string): Promise<ObserverConfig> {
  return parseConfig(JSON.parse(await readFile(path, "utf8")));
}
