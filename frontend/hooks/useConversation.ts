"use client";

import { useCallback, useState } from "react";
import { getConversation, sendChatMessage } from "@/lib/api";
import type {
  ChatPlannerOut,
  ChatTurn,
  ConversationDetailResponse,
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

    turns.push({
      id: assistantMsg?.id ?? makeId(),
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
}

export function useConversation() {
  const [state, setState] = useState<ConversationState>({
    conversationId: null,
    conversationTitle: null,
    turns: [],
  });

  const { conversationId, conversationTitle, turns } = state;
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
          turns: prev.turns.map((t) =>
            t.id === tempId
              ? {
                  id: response.assistant_message.id,
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
    setState({ conversationId: id, conversationTitle: null, turns: [] });
    try {
      const detail = await getConversation(id);
      setState({
        conversationId: id,
        conversationTitle: detail.conversation.title,
        turns: reconstructTurns(detail),
      });
    } catch {
      setState({ conversationId: null, conversationTitle: null, turns: [] });
    }
  }, []);

  // Update the title in local state (called after a successful rename).
  const updateTitle = useCallback((newTitle: string) => {
    setState((prev) => ({ ...prev, conversationTitle: newTitle }));
  }, []);

  // Start a fresh conversation.
  const reset = useCallback(() => {
    setState({ conversationId: null, conversationTitle: null, turns: [] });
  }, []);

  return { conversationId, conversationTitle, turns, isLoading, sendMessage, loadConversation, updateTitle, reset };
}
