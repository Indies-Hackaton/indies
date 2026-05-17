"use client";

import { useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import type { ChatTurn } from "@/lib/types";
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

// Applies marker parsing to a ReactMarkdown paragraph's string children.
function makeParagraphComponent(onMarkerClick: (n: number) => void): Components["p"] {
  return function Paragraph({ children }) {
    const processed = typeof children === "string"
      ? parseMarkers(children, onMarkerClick)
      : children;
    return <p>{processed}</p>;
  };
}

// ── Content renderer ──────────────────────────────────────────────

function renderContent(
  content: string,
  format: string,
  onMarkerClick: (n: number) => void,
) {
  if (format === "markdown") {
    return (
      <div className={styles.markdown}>
        <ReactMarkdown
          components={{ p: makeParagraphComponent(onMarkerClick) }}
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

// ── Typing indicator ──────────────────────────────────────────────

function TypingIndicator() {
  return (
    <span className={styles.typing} aria-label="Procesando">
      <span className={styles.dot} />
      <span className={styles.dot} />
      <span className={styles.dot} />
    </span>
  );
}

// ── Component ─────────────────────────────────────────────────────

interface MessageBubbleProps {
  turn: ChatTurn;
}

export function MessageBubble({ turn }: MessageBubbleProps) {
  const { question, assistantMessage, status, error } = turn;
  const [activeSourceIndex, setActiveSourceIndex] = useState<number | null>(null);

  function handleMarkerClick(n: number) {
    // Toggle off if clicking the same marker twice.
    setActiveSourceIndex((prev) => (prev === n ? null : n));
  }

  return (
    <div className={styles.turn}>

      {/* ── User bubble ── */}
      <div className={styles.userRow}>
        <div className={styles.userBubble}>
          <p className={styles.userText}>{question}</p>
        </div>
      </div>

      {/* ── Assistant bubble ── */}
      <div className={styles.assistantRow}>
        <div className={styles.assistantLabel}>INDIES</div>

        <div className={styles.assistantBubble}>
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
      </div>

      {/* ── Sources section ── */}
      {status === "success" && turn.toolRuns.length > 0 && (
        <div className={styles.sourcesRow}>
          <SourcesSection
            toolRuns={turn.toolRuns}
            totalRecords={turn.totalRecords}
            messageId={turn.id}
            activeIndex={activeSourceIndex}
          />
        </div>
      )}

    </div>
  );
}
