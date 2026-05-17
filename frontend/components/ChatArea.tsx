"use client";

import { useEffect, useRef } from "react";
import type { ChatTurn } from "@/lib/types";
import { ChatInput } from "./ChatInput";
import { ExampleChips } from "./ExampleChips";
import { MessageBubble } from "./MessageBubble";
import styles from "./ChatArea.module.css";

interface ChatAreaProps {
  turns: ChatTurn[];
  isLoading: boolean;
  title: string | null;
  onSubmit: (message: string) => void;
  onOpenPanel: (turn: ChatTurn) => void;
}

export function ChatArea({ turns, isLoading, title, onSubmit, onOpenPanel }: ChatAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns.length]);

  return (
    <div className={styles.area}>

      {/* ── Conversation title bar — only when a conversation is active ── */}
      {title && (
        <div className={styles.titleBar}>
          <span className={styles.titleText}>{title}</span>
        </div>
      )}

      {/* ── Message thread ── */}
      <div className={styles.thread}>
        {turns.length === 0 ? (
          <ExampleChips onSelect={onSubmit} />
        ) : (
          <div className={styles.messages}>
            {turns.map((turn) => (
              <MessageBubble
                key={turn.id}
                turn={turn}
                onOpenPanel={onOpenPanel}
              />
            ))}
            <div ref={bottomRef} aria-hidden="true" />
          </div>
        )}
      </div>

      {/* ── Input ── */}
      <ChatInput onSubmit={onSubmit} disabled={isLoading} />

    </div>
  );
}
