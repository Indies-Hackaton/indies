import type {
  ChatMessageResponse,
  ConversationDetailResponse,
  ConversationListItem,
  ConversationOut,
  FeedbackRating,
  MessageOut,
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

// token is passed explicitly from the calling hook — Clerk's recommended pattern.
async function request<T>(
  path: string,
  token: string | null,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${baseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ── Chat endpoints ────────────────────────────────────────────────────────

export function sendChatMessage(
  message: string,
  conversationId: string | null,
  token: string | null,
): Promise<ChatMessageResponse> {
  return request<ChatMessageResponse>("/api/v1/chat/messages", token, {
    method: "POST",
    body: JSON.stringify({
      message,
      conversation_id: conversationId ?? undefined,
    }),
  });
}

export function listConversations(token: string | null): Promise<ConversationListItem[]> {
  return request<ConversationListItem[]>("/api/v1/chat/conversations", token);
}

export function getConversation(
  conversationId: string,
  token: string | null,
): Promise<ConversationDetailResponse> {
  return request<ConversationDetailResponse>(
    `/api/v1/chat/conversations/${conversationId}`,
    token,
  );
}

export function renameConversation(
  conversationId: string,
  title: string,
  token: string | null,
): Promise<ConversationOut> {
  return request<ConversationOut>(
    `/api/v1/chat/conversations/${conversationId}`,
    token,
    { method: "PATCH", body: JSON.stringify({ title }) },
  );
}

export function deleteConversation(
  conversationId: string,
  token: string | null,
): Promise<void> {
  return request<void>(
    `/api/v1/chat/conversations/${conversationId}`,
    token,
    { method: "DELETE" },
  );
}

export function submitMessageFeedback(
  messageId: string,
  feedbackRating: FeedbackRating | null,
  token: string | null,
): Promise<MessageOut> {
  return request<MessageOut>(
    `/api/v1/chat/messages/${messageId}/feedback`,
    token,
    { method: "PATCH", body: JSON.stringify({ feedback_rating: feedbackRating }) },
  );
}
