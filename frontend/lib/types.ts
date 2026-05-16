export type IntentTool =
  | "orders_by_org_and_date"
  | "orders_by_date"
  | "unknown";

export interface IntentParameters {
  codigoorg: string | null;
  fecha: string | null;
}

export interface Intent {
  tool: IntentTool;
  parameters: IntentParameters;
  reasoning: string | null;
}

export interface QueryResponse {
  intent: Intent;
  data: Record<string, unknown> | null;
  detail: string | null;
}

export type QueryStatus = "loading" | "success" | "error" | "unknown-intent";

export interface QueryEntry {
  id: string;
  timestamp: Date;
  question: string;
  response: QueryResponse | null;
  status: QueryStatus;
  error: string | null;
}
