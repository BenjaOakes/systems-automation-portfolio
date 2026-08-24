import type { AgentEvent } from "../types.js";
import { createHash } from "node:crypto";

const secretPatterns: readonly [RegExp, string][] = [
  [/\bBearer\s+[A-Za-z0-9._~+/=-]+/gi, "Bearer [REDACTED_TOKEN]"],
  [/(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*[^\s,;]+/gi, "[REDACTED_SECRET]"],
  [/\b[A-Za-z0-9_-]{24,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b/g, "[REDACTED_JWT]"],
  [/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[REDACTED_EMAIL]"],
];

const windowsPath = /\b[A-Za-z]:\\[^"'\r\n]+/g;
const uncPath = /\\\\[^\s"']+\\[^\s"']*/g;
const unixPath = /\/(?:Users|home|private|var)\/[^"'\r\n]+/g;

const safeSourcePattern = /^source-[a-f0-9]{64}$/;

/** Return a deterministic identifier that cannot disclose the source path. */
export function safeSourceIdentifier(source: string): string {
  if (safeSourcePattern.test(source)) return source;
  return `source-${createHash("sha256").update(source, "utf8").digest("hex")}`;
}

/** Hash session keys by default so a vendor-specific identifier cannot become a report key. */
export function safeSessionIdentifier(sessionId: string, hash = true): string {
  if (!hash) return sessionId;
  return `session-${createHash("sha256").update(sessionId, "utf8").digest("hex")}`;
}

export function redactText(text: string, redactLocalPaths = true): string {
  let result = text;
  for (const [pattern, replacement] of secretPatterns) result = result.replace(pattern, replacement);
  if (redactLocalPaths) result = result.replace(windowsPath, "[REDACTED_LOCAL_PATH]").replace(uncPath, "[REDACTED_LOCAL_PATH]").replace(unixPath, "[REDACTED_LOCAL_PATH]");
  return result;
}

export function redactEvent(event: AgentEvent, redactLocalPaths = true): AgentEvent {
  return {
    ...event,
    content: redactText(event.content, redactLocalPaths),
    source: safeSourceIdentifier(event.source),
  };
}
