"use client";

import { useCallback, useState } from "react";
import { submitQuery } from "@/lib/api";
import type { QueryEntry } from "@/lib/types";

function makeId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function useQueryHistory() {
  // Phase 2: swap useState for a localStorage-backed initialiser here.
  // Phase 3: swap add/clear for API calls here.
  // Component code never changes.
  const [entries, setEntries] = useState<QueryEntry[]>([]);

  const submit = useCallback(async (question: string) => {
    const id = makeId();

    const placeholder: QueryEntry = {
      id,
      timestamp: new Date(),
      question,
      response: null,
      status: "loading",
      error: null,
    };

    setEntries((prev) => [placeholder, ...prev]);

    try {
      const response = await submitQuery(question);
      setEntries((prev) =>
        prev.map((e) => (e.id === id ? { ...e, response, status: "success" } : e)),
      );
    } catch (err) {
      const error =
        err instanceof Error ? err.message : "Error desconocido.";
      setEntries((prev) =>
        prev.map((e) =>
          e.id === id ? { ...e, status: "error", error } : e,
        ),
      );
    }
  }, []);

  const clear = useCallback(() => setEntries([]), []);

  return { entries, submit, clear };
}
