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
import type { ChatTurn } from "@/lib/types";
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

interface MessageBubbleProps {
  turn: ChatTurn;
}

export function MessageBubble({ turn }: MessageBubbleProps) {
  const { question, assistantMessage, status, error } = turn;
  const [activeSourceIndex, setActiveSourceIndex] = useState<number | null>(null);

  function handleMarkerClick(n: number) {
    setActiveSourceIndex((prev) => (prev === n ? null : n));
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

          {status === "success" && turn.toolRuns.length > 0 && (
            <SourcesSection
              toolRuns={turn.toolRuns}
              totalRecords={turn.totalRecords}
              messageId={turn.id}
              activeIndex={activeSourceIndex}
            />
          )}
        </div>
      </div>

    </div>
  );
}
