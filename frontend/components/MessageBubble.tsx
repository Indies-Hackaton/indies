import ReactMarkdown from "react-markdown";
import type { ChatTurn } from "@/lib/types";
import { SourcesSection } from "./SourcesSection";
import styles from "./MessageBubble.module.css";

interface MessageBubbleProps {
  turn: ChatTurn;
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

// TODO: when the backend delivers [N] citation markers in the synthesis text,
// replace this with a parser that wraps each [N] in a <button> that scrolls
// to and highlights source-{messageId}-{N} in the SourcesSection below.
function renderContent(content: string, format: string) {
  if (format === "markdown") {
    return (
      <div className={styles.markdown}>
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    );
  }
  return <p className={styles.assistantText}>{content}</p>;
}

export function MessageBubble({ turn }: MessageBubbleProps) {
  const { question, assistantMessage, status, error } = turn;

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
          />
        </div>
      )}

    </div>
  );
}
