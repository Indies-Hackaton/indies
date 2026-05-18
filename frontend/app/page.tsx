"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useConversation } from "@/hooks/useConversation";
import { useConversations } from "@/hooks/useConversations";
import { useTheme } from "@/hooks/useTheme";
import { deleteConversation, renameConversation } from "@/lib/api";
import { ChatArea } from "@/components/ChatArea";
import { ConfirmDeleteModal } from "@/components/ConfirmDeleteModal";
import { BrandLogo } from "@/components/BrandLogo";
import { Sidebar } from "@/components/Sidebar";
import { UserButton, useAuth, useUser } from "@clerk/nextjs";
import { ThemeToggle } from "@/components/ThemeToggle";
import styles from "./page.module.css";

export default function Home() {
  const conversation = useConversation();
  const conversations = useConversations();
  const { theme, setTheme } = useTheme();
  const { isSignedIn } = useUser();
  const { getToken } = useAuth();
  /** Ancho de la columna (rail 44px ↔ panel 260px en desktop). */
  const [sidebarWide, setSidebarWide] = useState(true);
  /** Lista y textos del panel; en desktop aparece solo cuando el ancho terminó de abrir. */
  const [sidebarDetail, setSidebarDetail] = useState(true);
  const sidebarColRef = useRef<HTMLDivElement>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const isMobileViewport = useCallback(
    () => typeof window !== "undefined" && window.innerWidth <= 768,
    [],
  );

  const closeSidebar = useCallback(() => {
    setSidebarDetail(false);
    setSidebarWide(false);
  }, []);

  const openSidebarMobile = useCallback(() => {
    setSidebarWide(true);
    setSidebarDetail(true);
  }, []);

  const toggleSidebar = useCallback(() => {
    if (isMobileViewport()) {
      if (sidebarWide) closeSidebar();
      else openSidebarMobile();
      return;
    }
    if (sidebarDetail) {
      setSidebarDetail(false);
      setSidebarWide(false);
      return;
    }
    setSidebarWide(true);
    const col = sidebarColRef.current;
    if (!col) {
      setSidebarDetail(true);
      return;
    }
    const raw = getComputedStyle(col).transitionDuration.split(",")[0]?.trim() ?? "0";
    const durationMs = raw.endsWith("ms")
      ? parseFloat(raw)
      : parseFloat(raw) * 1000;
    if (!durationMs || col.offsetWidth >= 260) {
      setSidebarDetail(true);
    }
  }, [closeSidebar, isMobileViewport, openSidebarMobile, sidebarDetail, sidebarWide]);

  useEffect(() => {
    const col = sidebarColRef.current;
    if (!col) return;

    function onTransitionEnd(e: TransitionEvent) {
      if (e.target !== col || isMobileViewport()) return;
      if (e.propertyName !== "width") return;
      if (sidebarWide) setSidebarDetail(true);
    }

    col.addEventListener("transitionend", onTransitionEnd);
    return () => col.removeEventListener("transitionend", onTransitionEnd);
  }, [isMobileViewport, sidebarWide]);

  async function handleSubmit(message: string) {
    await conversation.sendMessage(message);
    conversations.refresh();
  }

  function handleSelectConversation(id: string) {
    conversation.loadConversation(id);
    if (isMobileViewport()) closeSidebar();
  }

  function handleNewConversation() {
    conversation.reset();
    if (isMobileViewport()) closeSidebar();
  }

  async function handleRename(id: string, newTitle: string) {
    const token = await getToken();
    await renameConversation(id, newTitle, token);
    if (id === conversation.conversationId) {
      conversation.updateTitle(newTitle);
    }
    conversations.refresh();
  }

  async function confirmDelete() {
    if (!pendingDeleteId) return;
    setIsDeleting(true);
    try {
      const token = await getToken();
      await deleteConversation(pendingDeleteId, token);
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
        <div className={styles.headerBrand}>
          <button
            className={styles.hamburger}
            type="button"
            onClick={toggleSidebar}
            aria-label="Abrir menú"
            aria-expanded={sidebarWide}
          >
            ☰
          </button>
          <BrandLogo mode="full" size="md" />
        </div>
        <p className={styles.tagline}>
          Mercado Público, Contraloría y Congreso · Chile
        </p>
        <div className={styles.headerRight}>
          <ThemeToggle theme={theme} onChange={setTheme} />
          <span className={styles.dateBadge}>
            {new Date().toLocaleDateString("es-CL", {
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
          </span>
          {isSignedIn && (
            <UserButton
              appearance={{
                elements: {
                  avatarBox: styles.clerkAvatar,
                },
              }}
            />
          )}
        </div>
      </header>

      {/* ── Body ── */}
      <div className={styles.body}>

        {sidebarWide && (
          <div
            className={styles.backdrop}
            onClick={closeSidebar}
            aria-hidden="true"
          />
        )}

        <div
          ref={sidebarColRef}
          className={`${styles.sidebarCol} ${sidebarWide ? styles.sidebarOpen : styles.sidebarClosed}`}
        >
          <Sidebar
            conversations={conversations.conversations}
            activeId={conversation.conversationId}
            isLoading={conversations.isLoading}
            isOpen={sidebarDetail}
            onToggle={toggleSidebar}
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
            isLoadingConversation={conversation.isLoadingConversation}
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
            onFeedback={conversation.updateTurnFeedback}
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
