import type { AgentEvent, SessionSummary } from "../types.js";

export function aggregateSessions(events: readonly AgentEvent[]): SessionSummary[] {
  const groups = new Map<string, AgentEvent[]>();
  for (const event of events) groups.set(event.sessionId, [...(groups.get(event.sessionId) ?? []), event]);
  return [...groups.entries()].map(([sessionId, items]) => {
    const ordered = [...items].sort((left, right) => left.timestamp.localeCompare(right.timestamp));
    const roles: Record<string, number> = {};
    for (const item of ordered) roles[item.role] = (roles[item.role] ?? 0) + 1;
    return {
      sessionId,
      agent: ordered[0].agent,
      eventCount: ordered.length,
      roles,
      firstSeen: ordered[0].timestamp,
      lastSeen: ordered[ordered.length - 1].timestamp,
      contentCharacters: ordered.reduce((total, item) => total + item.content.length, 0),
    };
  }).sort((left, right) => left.sessionId.localeCompare(right.sessionId));
}
