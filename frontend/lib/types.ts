// ── Shared pipeline models (mirrors backend/app/services/models.py) ──────

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

// ── Chat / conversation models (mirrors backend/app/services/models.py) ──

export interface ConversationOut {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface MessageOut {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  status: "processing" | "completed" | "failed";
  created_at: string;
  updated_at: string;
  linked_invocation_ids: string[];
  linked_tool_run_ids: string[];
}

export interface LlmInvocationOut {
  id: string;
  conversation_id: string;
  assistant_message_id: string | null;
  purpose: "title_generation" | "planner" | "chat_response";
  model: string;
  request_json: Record<string, unknown>;
  response_json: Record<string, unknown> | null;
  status: "ok" | "error";
  error: string | null;
  created_at: string;
}

export interface ToolRunOut {
  id: string;
  conversation_id: string;
  assistant_message_id: string;
  planner_invocation_id: string;
  task_id: string;
  tool: string;
  parameters: Record<string, unknown>;
  result: TaskResult;
  status: "ok" | "error";
  error: string | null;
  record_count: number;
  created_at: string;
}

export interface ChatPlannerOut {
  invocation_id: string;
  plan: Plan;
}

export interface ChatMessageResponse {
  conversation: ConversationOut;
  user_message: MessageOut;
  assistant_message: MessageOut;
  planner: ChatPlannerOut | null;
  tool_runs: ToolRunOut[];
  total_records: number;
}

export interface ConversationListItem extends ConversationOut {
  last_message: MessageOut | null;
  message_count: number;
}

export interface ConversationDetailResponse {
  conversation: ConversationOut;
  messages: MessageOut[];
  llm_invocations: LlmInvocationOut[];
  tool_runs: ToolRunOut[];
}

// ── Frontend-only models ─────────────────────────────────────────────────

/** A fully resolved chat turn held in local state. */
export interface ChatTurn {
  /** Unique turn id — matches assistant_message.id once resolved. */
  id: string;
  userMessage: MessageOut | null;
  assistantMessage: MessageOut | null;
  planner: ChatPlannerOut | null;
  toolRuns: ToolRunOut[];
  totalRecords: number;
  /** Optimistic question text shown before the server responds. */
  question: string;
  status: "loading" | "success" | "error";
  error: string | null;
}
