"use client";

import { useCallback, useEffect, useState } from "react";
import { listConversations } from "@/lib/api";
import type { ConversationListItem } from "@/lib/types";

interface State {
  conversations: ConversationListItem[];
  isLoading: boolean;
  error: string | null;
}

export function useConversations() {
  const [state, setState] = useState<State>({
    conversations: [],
    isLoading: true,
    error: null,
  });

  // Incrementing this triggers a re-fetch without requiring the caller
  // to manage its own effect dependency.
  const [fetchTick, setFetchTick] = useState(0);

  useEffect(() => {
    let cancelled = false;

    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    listConversations()
      .then((conversations) => {
        if (!cancelled) {
          setState({ conversations, isLoading: false, error: null });
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const error =
            err instanceof Error ? err.message : "Error al cargar conversaciones.";
          setState((prev) => ({ ...prev, isLoading: false, error }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [fetchTick]);

  // Call this after a new conversation is created or a message is sent,
  // so the sidebar stays in sync with the backend.
  const refresh = useCallback(() => setFetchTick((n) => n + 1), []);

  return { ...state, refresh };
}
