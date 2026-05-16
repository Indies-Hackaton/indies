"use client";

import { useEffect, useRef } from "react";
import { useQueryHistory } from "@/hooks/useQueryHistory";
import { SearchBar } from "@/components/SearchBar";
import { ExampleChips } from "@/components/ExampleChips";
import { ReceiptCard } from "@/components/ReceiptCard";
import styles from "./page.module.css";

export default function Home() {
  const { entries, submit, clear } = useQueryHistory();
  const feedRef = useRef<HTMLDivElement>(null);
  const isLoading = entries.some((e) => e.status === "loading");

  // Scroll feed to top whenever a new entry is added (newest card is at top).
  useEffect(() => {
    if (entries.length > 0) {
      feedRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, [entries.length]);

  function handleSubmit(message: string) {
    submit(message);
  }

  return (
    <div className={styles.page}>

      {/* ── Header ── */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.logo}>
            IN<span className={styles.logoAccent}>D</span>IES
          </span>
          <span className={styles.tagline}>
            Transparencia en compras públicas · Chile
          </span>
        </div>
        <div className={styles.headerRight}>
          <span className={styles.dateBadge}>
            {new Date().toLocaleDateString("es-CL", {
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
          </span>
          {entries.length > 0 && (
            <button
              className={styles.clearBtn}
              onClick={clear}
              type="button"
              disabled={isLoading}
            >
              Limpiar
            </button>
          )}
        </div>
      </header>

      {/* ── Search zone ── */}
      <div className={styles.searchZone}>
        <SearchBar onSubmit={handleSubmit} disabled={isLoading} />
      </div>

      {/* ── Feed ── */}
      <main className={styles.feed} ref={feedRef}>
        {entries.length === 0 ? (
          <ExampleChips onSelect={handleSubmit} />
        ) : (
          <div className={styles.feedInner}>
            {entries.map((entry, i) => (
              <ReceiptCard key={entry.id} entry={entry} index={entries.length - i} />
            ))}
          </div>
        )}
      </main>

    </div>
  );
}
