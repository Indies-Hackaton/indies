"use client";

import { useState } from "react";
import { useConversation } from "@/hooks/useConversation";
import { useConversations } from "@/hooks/useConversations";
import { deleteConversation, renameConversation } from "@/lib/api";
import { ChatArea } from "@/components/ChatArea";
import { ConfirmDeleteModal } from "@/components/ConfirmDeleteModal";
import { Sidebar } from "@/components/Sidebar";
import styles from "./page.module.css";

export default function Home() {
  const conversation = useConversation();
  const conversations = useConversations();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  async function handleSubmit(message: string) {
    await conversation.sendMessage(message);
    conversations.refresh();
  }

  function handleSelectConversation(id: string) {
    conversation.loadConversation(id);
    if (window.innerWidth < 768) setSidebarOpen(false);
  }

  function handleNewConversation() {
    conversation.reset();
    if (window.innerWidth < 768) setSidebarOpen(false);
  }

  async function handleRename(id: string, newTitle: string) {
    await renameConversation(id, newTitle);
    if (id === conversation.conversationId) {
      conversation.updateTitle(newTitle);
    }
    conversations.refresh();
  }

  async function confirmDelete() {
    if (!pendingDeleteId) return;
    setIsDeleting(true);
    try {
      await deleteConversation(pendingDeleteId);
      if (pendingDeleteId === conversation.conversationId) {
        conversation.reset();
      }
      conversations.refresh();
    } finally {
      setIsDeleting(false);
      setPendingDeleteId(null);
    }
  }

  const pendingDeleteTitle =
    conversations.conversations.find((c) => c.id === pendingDeleteId)?.title ??
    conversation.conversationTitle ??
    "esta conversación";

  return (
    <div className={styles.page}>

      {/* ── Header ── */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <button
            className={styles.hamburger}
            type="button"
            onClick={() => setSidebarOpen((v) => !v)}
            aria-label="Abrir menú"
            aria-expanded={sidebarOpen}
          >
            ☰
          </button>
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
        </div>
      </header>

      {/* ── Body ── */}
      <div className={styles.body}>

        {sidebarOpen && (
          <div
            className={styles.backdrop}
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        <div className={`${styles.sidebarCol} ${sidebarOpen ? styles.sidebarOpen : styles.sidebarClosed}`}>
          <Sidebar
            conversations={conversations.conversations}
            activeId={conversation.conversationId}
            isLoading={conversations.isLoading}
            isOpen={sidebarOpen}
            onToggle={() => setSidebarOpen((v) => !v)}
            onSelect={handleSelectConversation}
            onNew={handleNewConversation}
            onRename={handleRename}
            onDeleteRequest={setPendingDeleteId}
          />
        </div>

        <div className={styles.chatCol}>
          <ChatArea
            turns={conversation.turns}
            isLoading={conversation.isLoading}
            title={conversation.conversationTitle}
            onSubmit={handleSubmit}
            onRename={(newTitle) =>
              conversation.conversationId
                ? handleRename(conversation.conversationId, newTitle)
                : Promise.resolve()
            }
            onDelete={() => {
              if (conversation.conversationId) {
                setPendingDeleteId(conversation.conversationId);
              }
              return Promise.resolve();
            }}
          />
        </div>

      </div>

      {/* ── Delete confirmation modal ── */}
      {pendingDeleteId && (
        <ConfirmDeleteModal
          title={pendingDeleteTitle}
          onConfirm={confirmDelete}
          onCancel={() => setPendingDeleteId(null)}
          isLoading={isDeleting}
        />
      )}

    </div>
  );
}
