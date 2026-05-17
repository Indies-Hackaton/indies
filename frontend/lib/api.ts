import type {
  ChatMessageResponse,
  ConversationDetailResponse,
  ConversationListItem,
  ConversationOut,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function baseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${baseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      // Auth header goes here in Phase 3:
      // "Authorization": `Bearer ${token}`,
      ...init.headers,
    },
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

  return res.json() as Promise<T>;
}

// ── Chat endpoints ───────────────────────────────────────────────────────

export function sendChatMessage(
  message: string,
  conversationId: string | null,
): Promise<ChatMessageResponse> {
  return request<ChatMessageResponse>("/api/v1/chat/messages", {
    method: "POST",
    body: JSON.stringify({
      message,
      conversation_id: conversationId ?? undefined,
    }),
  });
}

export function listConversations(): Promise<ConversationListItem[]> {
  return request<ConversationListItem[]>("/api/v1/chat/conversations");
}

export function getConversation(
  conversationId: string,
): Promise<ConversationDetailResponse> {
  return request<ConversationDetailResponse>(
    `/api/v1/chat/conversations/${conversationId}`,
  );
}

export function renameConversation(
  conversationId: string,
  title: string,
): Promise<ConversationOut> {
  return request<ConversationOut>(
    `/api/v1/chat/conversations/${conversationId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ title }),
    },
  );
}

export function deleteConversation(conversationId: string): Promise<void> {
  return request<void>(`/api/v1/chat/conversations/${conversationId}`, {
    method: "DELETE",
  });
}
