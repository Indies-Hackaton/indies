"use client";

import { useState } from "react";
import { useConversation } from "@/hooks/useConversation";
import { useConversations } from "@/hooks/useConversations";
import type { ChatTurn } from "@/lib/types";
import { ChatArea } from "@/components/ChatArea";
import { ReceiptPanel } from "@/components/ReceiptPanel";
import { Sidebar } from "@/components/Sidebar";
import styles from "./page.module.css";

export default function Home() {
  const conversation = useConversation();
  const conversations = useConversations();
  const [panelTurn, setPanelTurn] = useState<ChatTurn | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  async function handleSubmit(message: string) {
    await conversation.sendMessage(message);
    conversations.refresh();
  }

  function handleSelectConversation(id: string) {
    setPanelTurn(null);
    conversation.loadConversation(id);
    // On mobile, close sidebar after selecting a conversation.
    if (window.innerWidth < 768) setSidebarOpen(false);
  }

  function handleNewConversation() {
    setPanelTurn(null);
    conversation.reset();
    if (window.innerWidth < 768) setSidebarOpen(false);
  }

  return (
    <div className={styles.page}>

      {/* ── Header ── */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          {/* Mobile hamburger — hidden on desktop */}
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

        {/* Mobile backdrop — closes sidebar when tapped */}
        {sidebarOpen && (
          <div
            className={styles.backdrop}
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        {/* Sidebar */}
        <div className={`${styles.sidebarCol} ${sidebarOpen ? styles.sidebarOpen : styles.sidebarClosed}`}>
          <Sidebar
            conversations={conversations.conversations}
            activeId={conversation.conversationId}
            isLoading={conversations.isLoading}
            isOpen={sidebarOpen}
            onToggle={() => setSidebarOpen((v) => !v)}
            onSelect={handleSelectConversation}
            onNew={handleNewConversation}
          />
        </div>

        {/* Chat */}
        <div className={styles.chatCol}>
          <ChatArea
            turns={conversation.turns}
            isLoading={conversation.isLoading}
            title={conversation.conversationTitle}
            onSubmit={handleSubmit}
            onOpenPanel={setPanelTurn}
          />
        </div>

        {/* Receipt panel */}
        {panelTurn && (
          <div className={styles.panelCol}>
            <ReceiptPanel
              turn={panelTurn}
              onClose={() => setPanelTurn(null)}
            />
          </div>
        )}

      </div>
    </div>
  );
}
