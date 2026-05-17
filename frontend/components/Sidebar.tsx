"use client";

import { useEffect, useRef, useState } from "react";
import type { ConversationListItem } from "@/lib/types";
import styles from "./Sidebar.module.css";

interface SidebarProps {
  conversations: ConversationListItem[];
  activeId: string | null;
  isLoading: boolean;
  isOpen: boolean;
  onToggle: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, newTitle: string) => Promise<void>;
  onDeleteRequest: (id: string) => void;
}

// ── Icons ─────────────────────────────────────────────────────────

function ComposeIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function SidebarPanelIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M9 3v18" />
    </svg>
  );
}

function DotsIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      <circle cx="5" cy="12" r="1.5" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none" />
      <circle cx="19" cy="12" r="1.5" fill="currentColor" stroke="none" />
    </svg>
  );
}

// ── Time grouping ─────────────────────────────────────────────────

const GROUP_ORDER = ["Hoy", "Ayer", "Últimos 7 días", "Últimos 30 días", "Anterior"];

function timeGroup(iso: string): string {
  const diffDays = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (diffDays < 1)  return "Hoy";
  if (diffDays < 2)  return "Ayer";
  if (diffDays < 7)  return "Últimos 7 días";
  if (diffDays < 30) return "Últimos 30 días";
  return "Anterior";
}

function groupConversations(conversations: ConversationListItem[]) {
  const map = new Map<string, ConversationListItem[]>();
  for (const conv of conversations) {
    const label = timeGroup(conv.updated_at);
    if (!map.has(label)) map.set(label, []);
    map.get(label)!.push(conv);
  }
  return GROUP_ORDER
    .filter((label) => map.has(label))
    .map((label) => ({ label, items: map.get(label)! }));
}

// ── Conversation item ─────────────────────────────────────────────

interface ConvItemProps {
  conv: ConversationListItem;
  isActive: boolean;
  onSelect: () => void;
  onRename: (newTitle: string) => Promise<void>;
  onDeleteRequest: () => void;
}

function ConvItem({ conv, isActive, onSelect, onRename, onDeleteRequest }: ConvItemProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close menu on outside click.
  useEffect(() => {
    if (!menuOpen) return;
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [menuOpen]);

  // Focus input when entering edit mode.
  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  function startEditing() {
    setEditValue(conv.title);
    setEditing(true);
    setMenuOpen(false);
  }

  function cancelEditing() {
    setEditing(false);
    setEditValue("");
  }

  async function commitRename() {
    const trimmed = editValue.trim();
    if (!trimmed || trimmed === conv.title) {
      cancelEditing();
      return;
    }
    setIsSaving(true);
    try {
      await onRename(trimmed);
    } finally {
      setIsSaving(false);
      setEditing(false);
    }
  }

  return (
    <div className={`${styles.itemWrap} ${isActive ? styles.itemWrapActive : ""}`}>
      {editing ? (
        <input
          ref={inputRef}
          className={styles.inlineInput}
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onBlur={commitRename}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitRename();
            if (e.key === "Escape") cancelEditing();
          }}
          disabled={isSaving}
          aria-label="Renombrar conversación"
        />
      ) : (
        <button
          className={styles.itemBtn}
          type="button"
          onClick={onSelect}
          aria-current={isActive ? "page" : undefined}
        >
          <span className={styles.itemTitle}>{conv.title}</span>
          <span className={styles.itemMeta}>{conv.message_count} msg</span>
        </button>
      )}

      {/* ── Three-dot menu ── */}
      {!editing && (
        <div className={styles.menuWrap} ref={menuRef}>
          <button
            className={styles.dotsBtn}
            type="button"
            onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v); }}
            aria-label="Opciones de conversación"
            aria-expanded={menuOpen}
          >
            <DotsIcon />
          </button>

          {menuOpen && (
            <div className={styles.dropdown}>
              <button
                className={styles.dropdownItem}
                type="button"
                onClick={startEditing}
              >
                Renombrar
              </button>
              <button
                className={`${styles.dropdownItem} ${styles.dropdownItemDanger}`}
                type="button"
                onClick={() => { setMenuOpen(false); onDeleteRequest(); }}
              >
                Eliminar
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────

export function Sidebar({
  conversations, activeId, isLoading, isOpen,
  onToggle, onSelect, onNew, onRename, onDeleteRequest,
}: SidebarProps) {
  const groups = groupConversations(conversations);

  return (
    <aside className={styles.sidebar}>

      <div className={isOpen ? styles.topBar : styles.topBarCollapsed}>
        {isOpen && <span className={styles.title}>Conversaciones</span>}
        <button
          className={styles.toggleBtn}
          type="button"
          onClick={onToggle}
          aria-label={isOpen ? "Colapsar panel" : "Expandir panel"}
        >
          <SidebarPanelIcon />
        </button>
      </div>

      {isOpen ? (
        <div className={styles.newBtnWrap}>
          <button className={styles.newBtn} type="button" onClick={onNew}>
            <ComposeIcon />
            Nueva conversación
          </button>
        </div>
      ) : (
        <div className={styles.collapsedNewWrap}>
          <button className={styles.collapsedNewBtn} type="button" onClick={onNew} aria-label="Nueva conversación">
            <ComposeIcon />
          </button>
        </div>
      )}

      {isOpen && (
        <div className={styles.list}>
          {isLoading && conversations.length === 0 && (
            <div className={styles.skeletonList}>
              {[68, 80, 55, 72, 60].map((w, i) => (
                <div key={i} className={styles.skeletonItem}>
                  <div className={styles.skeletonLine} style={{ width: `${w}%` }} />
                  <div className={styles.skeletonLine} style={{ width: "30%" }} />
                </div>
              ))}
            </div>
          )}

          {!isLoading && conversations.length === 0 && (
            <p className={styles.empty}>
              Sin conversaciones aún.<br />Empieza una nueva arriba.
            </p>
          )}

          {groups.map(({ label, items }) => (
            <div key={label} className={styles.group}>
              <p className={styles.groupLabel}>{label}</p>
              {items.map((conv) => (
                <ConvItem
                  key={conv.id}
                  conv={conv}
                  isActive={conv.id === activeId}
                  onSelect={() => onSelect(conv.id)}
                  onRename={(newTitle) => onRename(conv.id, newTitle)}
                  onDeleteRequest={() => onDeleteRequest(conv.id)}
                />
              ))}
            </div>
          ))}
        </div>
      )}

    </aside>
  );
}
