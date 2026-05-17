import type { ChatTurn, ToolRunOut } from "@/lib/types";
import { DataRenderer } from "./DataRenderer";
import styles from "./ReceiptPanel.module.css";

interface ReceiptPanelProps {
  turn: ChatTurn | null;
  onClose: () => void;
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <h3 className={styles.sectionLabel}>{children}</h3>;
}

function ToolRunBlock({ run }: { run: ToolRunOut }) {
  return (
    <div
      className={
        run.status === "error"
          ? `${styles.runBlock} ${styles.runBlockError}`
          : styles.runBlock
      }
    >
      <div className={styles.runHeader}>
        <span className={styles.badge}>{run.tool}</span>
        <span className={styles.runDesc}>{run.result.description}</span>
        {run.status === "ok" && (
          <span className={styles.runCount}>{run.record_count} reg.</span>
        )}
      </div>

      {run.status === "error" && (
        <p className={styles.runError}>{run.error ?? run.result.error}</p>
      )}

      {run.status === "ok" && run.result.records.length > 0 && (
        <DataRenderer records={run.result.records} />
      )}

      {run.status === "ok" && run.result.records.length === 0 && (
        <p className={styles.runEmpty}>Sin registros para esta tarea.</p>
      )}
    </div>
  );
}

export function ReceiptPanel({ turn, onClose }: ReceiptPanelProps) {
  if (!turn) return null;

  const { planner, toolRuns, totalRecords } = turn;

  return (
    <aside className={styles.panel}>

      {/* ── Panel header ── */}
      <div className={styles.panelHeader}>
        <div className={styles.panelHeaderLeft}>
          <span className={styles.panelTitle}>Recibo completo</span>
          {totalRecords > 0 && (
            <span className={styles.panelMeta}>
              {totalRecords} registro{totalRecords !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        <button
          className={styles.closeBtn}
          type="button"
          onClick={onClose}
          aria-label="Cerrar panel"
        >
          ×
        </button>
      </div>

      {/* ── Scrollable body ── */}
      <div className={styles.panelBody}>

        {/* Original question */}
        <section className={styles.section}>
          <SectionLabel>Pregunta</SectionLabel>
          <p className={styles.question}>{turn.question}</p>
        </section>

        {/* Agent plan */}
        {planner?.plan && (
          <section className={styles.section}>
            <SectionLabel>Plan del agente</SectionLabel>
            <p className={styles.reasoning}>{planner.plan.reasoning}</p>
            <ol className={styles.taskList}>
              {planner.plan.tasks?.map((task) => (
                <li key={task.id} className={styles.taskItem}>
                  <span className={styles.badge}>{task.tool}</span>
                  <p className={styles.taskDesc}>{task.description}</p>
                </li>
              ))}
            </ol>
          </section>
        )}

        {/* Tool run results */}
        <section className={styles.section}>
          <SectionLabel>
            Resultados · {totalRecords} registro{totalRecords !== 1 ? "s" : ""}
          </SectionLabel>
          <div className={styles.runList}>
            {toolRuns.map((run) => (
              <ToolRunBlock key={run.id} run={run} />
            ))}
          </div>
        </section>

        {/* Synthesis */}
        {turn.assistantMessage && (
          <section className={styles.section}>
            <SectionLabel>Síntesis</SectionLabel>
            <p className={styles.synthesis}>{turn.assistantMessage.content}</p>
          </section>
        )}

      </div>
    </aside>
  );
}
