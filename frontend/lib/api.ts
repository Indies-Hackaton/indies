import type { QueryResponse } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function submitQuery(message: string): Promise<QueryResponse> {
  const baseUrl =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  const res = await fetch(`${baseUrl}/api/v1/audit/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      // Auth header goes here in Phase 3:
      // "Authorization": `Bearer ${token}`,
    },
    body: JSON.stringify({ message }),
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore parse errors, keep the status code message
    }
    throw new ApiError(detail, res.status);
  }

  return res.json() as Promise<QueryResponse>;
}
