// ── Backend models (mirrors backend/app/services/models.py) ──────────────

export interface Task {
  id: string;
  tool: string;
  description: string;
  parameters: Record<string, unknown>;
}

export interface Plan {
  tasks: Task[];
  reasoning: string;
}

export interface TaskResult {
  task_id: string;
  tool: string;
  description: string;
  status: "ok" | "error";
  records: Record<string, unknown>[];
  record_count: number;
  metadata: Record<string, unknown>;
  error: string | null;
}

export interface AuditResponse {
  plan: Plan;
  results: TaskResult[];
  synthesis: string;
  total_records: number;
}

// ── Frontend-only models ─────────────────────────────────────────────────

export type QueryStatus = "loading" | "success" | "error";

export interface QueryEntry {
  id: string;
  timestamp: Date;
  question: string;
  response: AuditResponse | null;
  status: QueryStatus;
  error: string | null;
}
