"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatTurn } from "@/lib/types";
import { ChatInput } from "./ChatInput";
import { ConfirmDeleteModal } from "./ConfirmDeleteModal";
import { ExampleChips } from "./ExampleChips";
import { MessageBubble } from "./MessageBubble";
import styles from "./ChatArea.module.css";

// ── Icons ─────────────────────────────────────────────────────────

function PencilIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  );
}

// ── Props ─────────────────────────────────────────────────────────

interface ChatAreaProps {
  turns: ChatTurn[];
  isLoading: boolean;
  title: string | null;
  onSubmit: (message: string) => void;
  onRename: (newTitle: string) => Promise<void>;
  onDelete: () => Promise<void>;
}

// ── Component ─────────────────────────────────────────────────────

export function ChatArea({
  turns, isLoading, title, onSubmit, onRename, onDelete,
}: ChatAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [isRenaming, setIsRenaming] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns.length]);

  // Focus the input when entering edit mode.
  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  function startEditing() {
    setEditValue(title ?? "");
    setEditing(true);
  }

  function cancelEditing() {
    setEditing(false);
    setEditValue("");
  }

  async function commitRename() {
    const trimmed = editValue.trim();
    if (!trimmed || trimmed === title) {
      cancelEditing();
      return;
    }
    setIsRenaming(true);
    try {
      await onRename(trimmed);
    } finally {
      setIsRenaming(false);
      setEditing(false);
    }
  }

  async function confirmDelete() {
    setIsDeleting(true);
    try {
      await onDelete();
    } finally {
      setIsDeleting(false);
      setShowDeleteModal(false);
    }
  }

  return (
    <div className={styles.area}>

      {/* ── Title bar ── */}
      {title && (
        <div className={styles.titleBar}>
          {editing ? (
            <input
              ref={inputRef}
              className={styles.titleInput}
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onBlur={commitRename}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitRename();
                if (e.key === "Escape") cancelEditing();
              }}
              disabled={isRenaming}
              aria-label="Renombrar conversación"
            />
          ) : (
            <span className={styles.titleText}>{title}</span>
          )}

          <div className={styles.titleActions}>
            <button
              className={styles.titleActionBtn}
              type="button"
              onClick={startEditing}
              disabled={editing || isRenaming}
              aria-label="Renombrar conversación"
              title="Renombrar"
            >
              <PencilIcon />
            </button>
            <button
              className={`${styles.titleActionBtn} ${styles.titleActionBtnDanger}`}
              type="button"
              onClick={() => setShowDeleteModal(true)}
              disabled={editing}
              aria-label="Eliminar conversación"
              title="Eliminar"
            >
              <TrashIcon />
            </button>
          </div>
        </div>
      )}

      {/* ── Message thread ── */}
      <div className={styles.thread}>
        {turns.length === 0 ? (
          <ExampleChips onSelect={onSubmit} />
        ) : (
          <div className={styles.messages}>
            {turns.map((turn) => (
              <MessageBubble key={turn.id} turn={turn} />
            ))}
            <div ref={bottomRef} aria-hidden="true" />
          </div>
        )}
      </div>

      {/* ── Input ── */}
      <ChatInput onSubmit={onSubmit} disabled={isLoading} />

      {/* ── Delete confirmation modal ── */}
      {showDeleteModal && title && (
        <ConfirmDeleteModal
          title={title}
          onConfirm={confirmDelete}
          onCancel={() => setShowDeleteModal(false)}
          isLoading={isDeleting}
        />
      )}

    </div>
  );
}
