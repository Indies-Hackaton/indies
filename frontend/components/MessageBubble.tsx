"use client";

import React, {
  Children,
  cloneElement,
  isValidElement,
  useState,
  type ElementType,
  type ReactElement,
  type ReactNode,
  type TableHTMLAttributes,
} from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { submitMessageFeedback } from "@/lib/api";
import type { ChatTurn, FeedbackRating } from "@/lib/types";
import { BrandLogo } from "./BrandLogo";
import { SourcesSection } from "./SourcesSection";
import styles from "./MessageBubble.module.css";

// ── Citation marker parser ────────────────────────────────────────

const MARKER_RE = /(\[\d+\])/g;

function parseMarkers(text: string, onMarkerClick: (n: number) => void): ReactNode[] {
  return text.split(MARKER_RE).map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      const n = parseInt(match[1], 10);
      return (
        <button
          key={i}
          className={styles.marker}
          type="button"
          onClick={() => onMarkerClick(n)}
          aria-label={`Ver fuente ${n}`}
        >
          {part}
        </button>
      );
    }
    return part;
  });
}

function processChildren(
  children: ReactNode,
  onMarkerClick: (n: number) => void,
): ReactNode {
  // Only process direct string/number children — never recurse into React
  // elements. Each element has its own CitationWrapper that handles its own
  // string children. Recursing causes double-processing and nested <button>s.
  return Children.map(children, (child) => {
    if (typeof child === "string") return parseMarkers(child, onMarkerClick);
    if (typeof child === "number") return parseMarkers(String(child), onMarkerClick);
    return child;
  });
}

function withCitationMarkers(
  Tag: ElementType,
  onMarkerClick: (n: number) => void,
) {
  return function CitationWrapper({
    children,
    ...props
  }: React.HTMLAttributes<HTMLElement> & { children?: ReactNode }) {
    const T = Tag as React.ElementType;
    return <T {...props}>{processChildren(children, onMarkerClick)}</T>;
  };
}

function MarkdownTable({
  children,
  ...props
}: TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className={styles.tableBlock}>
      <p className={styles.tableScrollHint}>Desliza horizontalmente para ver todas las columnas</p>
      <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Tabla en la respuesta">
        <table className={styles.mdTable} {...props}>
          {children}
        </table>
      </div>
    </div>
  );
}

function markdownComponents(onMarkerClick: (n: number) => void): Components {
  const wrap = (tag: ElementType) =>
    withCitationMarkers(tag, onMarkerClick);

  return {
    p: wrap("p"),
    li: wrap("li"),
    h1: wrap("h1"),
    h2: wrap("h2"),
    h3: wrap("h3"),
    h4: wrap("h4"),
    strong: wrap("strong"),
    em: wrap("em"),
    td: wrap("td"),
    th: wrap("th"),
    blockquote: wrap("blockquote"),
    table: MarkdownTable,
  };
}

function renderContent(
  content: string,
  format: string,
  onMarkerClick: (n: number) => void,
) {
  if (format === "markdown") {
    return (
      <div className={styles.markdown}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={markdownComponents(onMarkerClick)}
        >
          {content}
        </ReactMarkdown>
      </div>
    );
  }
  return (
    <p className={styles.assistantText}>
      {parseMarkers(content, onMarkerClick)}
    </p>
  );
}

function UserAvatar() {
  return (
    <span className={styles.userAvatar} title="Tu cuenta" aria-hidden>
      <span className={styles.userAvatarImage}>
        <svg viewBox="0 0 24 24" fill="none" aria-hidden>
          <circle cx="12" cy="8" r="4" fill="currentColor" opacity="0.35" />
          <path
            d="M5 20c0-3.866 3.134-7 7-7s7 3.134 7 7"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
          />
        </svg>
      </span>
      <span className={styles.userAvatarStatus} aria-hidden />
    </span>
  );
}

function AssistantAvatar() {
  return (
    <span className={styles.assistantAvatar} aria-hidden>
      <BrandLogo mode="icon" size="sm" />
    </span>
  );
}

function TypingIndicator() {
  return (
    <span className={styles.typing} aria-label="Procesando">
      <span className={styles.dot} />
      <span className={styles.dot} />
      <span className={styles.dot} />
    </span>
  );
}

// ── Feedback buttons ──────────────────────────────────────────────

function ThumbUpIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z" />
      <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
    </svg>
  );
}

function ThumbDownIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z" />
      <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
    </svg>
  );
}

interface FeedbackButtonsProps {
  messageId: string;
  currentRating: FeedbackRating | null;
  onRate: (rating: FeedbackRating | null) => void;
}

function FeedbackButtons({ messageId, currentRating, onRate }: FeedbackButtonsProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleClick(rating: FeedbackRating) {
    if (isSubmitting) return;
    const next = currentRating === rating ? null : rating;
    setIsSubmitting(true);
    try {
      await submitMessageFeedback(messageId, next);
      onRate(next);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className={styles.feedback}>
      <button
        className={`${styles.feedbackBtn} ${currentRating === "like" ? styles.feedbackBtnActive : ""}`}
        type="button"
        onClick={() => handleClick("like")}
        disabled={isSubmitting}
        aria-pressed={currentRating === "like"}
      >
        <ThumbUpIcon />
        Útil
      </button>
      <button
        className={`${styles.feedbackBtn} ${currentRating === "dislike" ? styles.feedbackBtnActive : ""}`}
        type="button"
        onClick={() => handleClick("dislike")}
        disabled={isSubmitting}
        aria-pressed={currentRating === "dislike"}
      >
        <ThumbDownIcon />
        No útil
      </button>
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────

interface MessageBubbleProps {
  turn: ChatTurn;
  onFeedback: (turnId: string, rating: FeedbackRating | null) => void;
}

export function MessageBubble({ turn, onFeedback }: MessageBubbleProps) {
  const { question, assistantMessage, status, error } = turn;
  const [activeSourceIndex, setActiveSourceIndex] = useState<number | null>(null);
  const [activeTick, setActiveTick] = useState(0);

  function handleMarkerClick(n: number) {
    // Always activate the clicked source (no toggle-off).
    // Increment tick so repeated clicks on the same marker re-trigger scroll.
    setActiveSourceIndex(n);
    setActiveTick((t) => t + 1);
  }

  return (
    <div className={styles.turn}>

      <div className={styles.userRow}>
        <div className={styles.userBubble}>
          <p className={styles.userText}>{question}</p>
        </div>
        <UserAvatar />
      </div>

      <div className={styles.assistantRow}>
        <div className={styles.assistantAside}>
          <AssistantAvatar />
        </div>
        <div className={styles.assistantContent}>
          <div className={styles.assistantBody}>
            {status === "loading" && <TypingIndicator />}

            {status === "error" && (
              <p className={styles.errorText}>
                {error ?? "Error al procesar la consulta."}
              </p>
            )}

            {status === "success" && assistantMessage && renderContent(
              assistantMessage.content,
              assistantMessage.content_format,
              handleMarkerClick,
            )}
          </div>

          {status === "success" && assistantMessage && (
            <FeedbackButtons
              messageId={assistantMessage.id}
              currentRating={assistantMessage.feedback_rating}
              onRate={(rating) => onFeedback(turn.id, rating)}
            />
          )}

          {status === "success" && turn.toolRuns.length > 0 && (
            <SourcesSection
              toolRuns={turn.toolRuns}
              totalRecords={turn.totalRecords}
              messageId={turn.id}
              activeIndex={activeSourceIndex}
              activeTick={activeTick}
            />
          )}
        </div>
      </div>

    </div>
  );
}
