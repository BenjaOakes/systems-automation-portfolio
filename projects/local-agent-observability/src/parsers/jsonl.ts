import type { AgentEvent, ParseResult } from "../types.js";
import { safeSessionIdentifier, safeSourceIdentifier } from "../privacy/redact.js";

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

export function parseJsonl(text: string, source = "memory", options: { hashSessionIds?: boolean } = {}): ParseResult {
  const events: AgentEvent[] = [];
  const issues: ParseResult["issues"] = [];
  const safeSource = safeSourceIdentifier(source);
  text.split(/\r?\n/).forEach((line, index) => {
    if (!line.trim()) return;
    try {
      const raw = JSON.parse(line) as Record<string, unknown>;
      const sessionId = stringValue(raw.sessionId ?? raw.session_id);
      const content = stringValue(raw.content ?? raw.message);
      const timestamp = stringValue(raw.timestamp ?? raw.createdAt);
      if (!sessionId || !content || !timestamp) throw new Error("sessionId, timestamp, and content are required");
      if (Number.isNaN(Date.parse(timestamp))) throw new Error("timestamp is not parseable");
      const roleValue = stringValue(raw.role);
      const roles = new Set(["user", "assistant", "system", "tool"]);
      const role = roles.has(roleValue ?? "") ? (roleValue as AgentEvent["role"]) : "unknown";
      events.push({
        sessionId: safeSessionIdentifier(sessionId, options.hashSessionIds !== false),
        agent: stringValue(raw.agent) ?? "unknown-agent",
        timestamp: new Date(timestamp).toISOString(),
        role,
        content,
        source: safeSource,
      });
    } catch (error) {
      issues.push({ source: safeSource, line: index + 1, reason: error instanceof Error ? error.message : "invalid JSONL record" });
    }
  });
  return { events, issues };
}
