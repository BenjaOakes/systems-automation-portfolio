export type AgentName = "synthetic-agent" | "unknown-agent" | (string & {});

export interface AgentEvent {
  readonly sessionId: string;
  readonly agent: AgentName;
  readonly timestamp: string;
  readonly role: "user" | "assistant" | "system" | "tool" | "unknown";
  readonly content: string;
  readonly source: string;
}

export interface ParseIssue {
  readonly source: string;
  readonly line: number;
  readonly reason: string;
}

export interface ParseResult {
  readonly events: AgentEvent[];
  readonly issues: ParseIssue[];
}

export interface ObserverConfig {
  readonly inputFiles: string[];
  readonly stateDirectory: string;
  readonly outputFile: string;
  readonly noNetwork: true;
  readonly redactLocalPaths: boolean;
  readonly hashSessionIds: boolean;
  readonly maxEvents: number;
}

export interface SessionSummary {
  readonly sessionId: string;
  readonly agent: string;
  readonly eventCount: number;
  readonly roles: Record<string, number>;
  readonly firstSeen: string;
  readonly lastSeen: string;
  readonly contentCharacters: number;
}
