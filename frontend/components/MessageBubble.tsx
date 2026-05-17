import type { ChatTurn } from "@/lib/types";
import { ReceiptInline } from "./ReceiptInline";
import styles from "./MessageBubble.module.css";

interface MessageBubbleProps {
  turn: ChatTurn;
  onOpenPanel: (turn: ChatTurn) => void;
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

export function MessageBubble({ turn, onOpenPanel }: MessageBubbleProps) {
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

          {status === "success" && assistantMessage && (
            <p className={styles.assistantText}>{assistantMessage.content}</p>
          )}
        </div>
      </div>

      {/* ── Inline receipt strip (success only) ── */}
      {status === "success" && (
        <div className={styles.receiptRow}>
          <ReceiptInline turn={turn} onOpenPanel={onOpenPanel} />
        </div>
      )}

    </div>
  );
}
