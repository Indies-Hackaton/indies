"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { listConversations } from "@/lib/api";
import type { ConversationListItem } from "@/lib/types";

interface State {
  conversations: ConversationListItem[];
  isLoading: boolean;
  error: string | null;
}

export function useConversations() {
  const { isLoaded, isSignedIn, getToken } = useAuth();

  const [state, setState] = useState<State>({
    conversations: [],
    isLoading: false,
    error: null,
  });

  const [fetchTick, setFetchTick] = useState(0);

  useEffect(() => {
    if (!isLoaded) return;

    if (!isSignedIn) {
      setState({ conversations: [], isLoading: false, error: null });
      return;
    }

    let cancelled = false;
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    // Get token then fetch — Clerk's recommended cross-origin pattern.
    getToken().then((token) => {
      if (cancelled) return;
      return listConversations(token);
    }).then((conversations) => {
      if (!cancelled && conversations) {
        setState({ conversations, isLoading: false, error: null });
      }
    }).catch((err) => {
      if (!cancelled) {
        const error = err instanceof Error ? err.message : "Error al cargar conversaciones.";
        setState((prev) => ({ ...prev, isLoading: false, error }));
      }
    });

    return () => { cancelled = true; };
  }, [fetchTick, isLoaded, isSignedIn, getToken]);

  const refresh = useCallback(() => setFetchTick((n) => n + 1), []);

  return { ...state, refresh };
}
