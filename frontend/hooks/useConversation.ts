"use client";

import { useCallback, useState } from "react";
import { getConversation, sendChatMessage } from "@/lib/api";
import type {
  ChatPlannerOut,
  ChatTurn,
  ConversationDetailResponse,
  FeedbackRating,
  Plan,
} from "@/lib/types";

function makeId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function reconstructTurns(detail: ConversationDetailResponse): ChatTurn[] {
  const turns: ChatTurn[] = [];

  for (let i = 0; i < detail.messages.length; i++) {
    const msg = detail.messages[i];
    if (msg.role !== "user") continue;

    const next = detail.messages[i + 1];
    const assistantMsg = next?.role === "assistant" ? next : null;

    const toolRuns = assistantMsg
      ? detail.tool_runs.filter((tr) =>
          assistantMsg.linked_tool_run_ids.includes(tr.id),
        )
      : [];

    // Reconstruct the planner from the linked LLM invocation.
    // response_json shape: { content: string, parsed: Plan, ... }
    // The Plan lives at response_json.parsed, not at the root.
    const plannerInv = assistantMsg
      ? detail.llm_invocations.find(
          (inv) =>
            inv.purpose === "planner" &&
            assistantMsg.linked_invocation_ids.includes(inv.id),
        )
      : null;

    const parsedPlan = (
      plannerInv?.response_json as { parsed?: Plan } | null
    )?.parsed;

    const planner: ChatPlannerOut | null =
      plannerInv && parsedPlan
        ? { invocation_id: plannerInv.id, plan: parsedPlan }
        : null;

    const stableId = assistantMsg?.id ?? makeId();
    turns.push({
      id: stableId,
      renderKey: stableId, // history turns: id and renderKey are the same
      question: msg.content,
      userMessage: msg,
      assistantMessage: assistantMsg,
      planner,
      toolRuns,
      totalRecords: toolRuns.reduce((sum, tr) => sum + tr.record_count, 0),
      status: assistantMsg ? "success" : "error",
      error: null,
    });
  }

  return turns;
}

interface ConversationState {
  conversationId: string | null;
  conversationTitle: string | null;
  turns: ChatTurn[];
  isLoadingConversation: boolean;
}

export function useConversation() {
  const [state, setState] = useState<ConversationState>({
    conversationId: null,
    conversationTitle: null,
    turns: [],
    isLoadingConversation: false,
  });

  const { conversationId, conversationTitle, turns, isLoadingConversation } = state;
  const isLoading = turns.some((t) => t.status === "loading");

  const sendMessage = useCallback(
    async (question: string) => {
      const tempId = makeId();

      // Add optimistic turn immediately so the bubble appears at once.
      setState((prev) => ({
        ...prev,
        turns: [
          ...prev.turns,
          {
            id: tempId,
            renderKey: tempId, // stable — never changes, prevents remount
            question,
            userMessage: null,
            assistantMessage: null,
            planner: null,
            toolRuns: [],
            totalRecords: 0,
            status: "loading",
            error: null,
          } satisfies ChatTurn,
        ],
      }));

      try {
        const response = await sendChatMessage(question, conversationId);

        setState((prev) => ({
          conversationId: response.conversation.id,
          conversationTitle: response.conversation.title,
          isLoadingConversation: false,
          turns: prev.turns.map((t) =>
            t.id === tempId
              ? {
                  id: response.assistant_message.id,
                  renderKey: tempId, // preserve the stable key
                  question,
                  userMessage: response.user_message,
                  assistantMessage: response.assistant_message,
                  planner: response.planner,
                  toolRuns: response.tool_runs,
                  totalRecords: response.total_records,
                  status: "success",
                  error: null,
                }
              : t,
          ),
        }));
      } catch (err) {
        const error =
          err instanceof Error ? err.message : "Error desconocido.";
        setState((prev) => ({
          ...prev,
          turns: prev.turns.map((t) =>
            t.id === tempId ? { ...t, status: "error", error } : t,
          ),
        }));
      }
    },
    // Recreate when conversationId changes so we never use a stale id.
    [conversationId],
  );

  // Load a past conversation from the sidebar.
  const loadConversation = useCallback(async (id: string) => {
    // Show skeleton instead of empty state while fetching.
    setState({ conversationId: id, conversationTitle: null, turns: [], isLoadingConversation: true });
    try {
      const detail = await getConversation(id);
      setState({
        conversationId: id,
        conversationTitle: detail.conversation.title,
        turns: reconstructTurns(detail),
        isLoadingConversation: false,
      });
    } catch {
      setState({ conversationId: null, conversationTitle: null, turns: [], isLoadingConversation: false });
    }
  }, []);

  // Update the title in local state (called after a successful rename).
  const updateTitle = useCallback((newTitle: string) => {
    setState((prev) => ({ ...prev, conversationTitle: newTitle }));
  }, []);

  // Patch the feedback rating on an assistant message in local state.
  const updateTurnFeedback = useCallback(
    (turnId: string, feedbackRating: FeedbackRating | null) => {
      setState((prev) => ({
        ...prev,
        turns: prev.turns.map((t) =>
          t.id === turnId && t.assistantMessage
            ? {
                ...t,
                assistantMessage: {
                  ...t.assistantMessage,
                  feedback_rating: feedbackRating,
                },
              }
            : t,
        ),
      }));
    },
    [],
  );

  // Start a fresh conversation.
  const reset = useCallback(() => {
    setState({ conversationId: null, conversationTitle: null, turns: [], isLoadingConversation: false });
  }, []);

  return { conversationId, conversationTitle, turns, isLoading, isLoadingConversation, sendMessage, loadConversation, updateTitle, updateTurnFeedback, reset };
}
