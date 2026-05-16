import type { QueryEntry, TaskResult } from "@/lib/types";
import { DataRenderer } from "./DataRenderer";
import { SynthesisContent } from "./SynthesisContent";
import styles from "./ReceiptCard.module.css";

interface ReceiptCardProps {
  entry: QueryEntry;
  index: number;
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <h3 className={styles.sectionLabel}>{children}</h3>;
}

function Skeleton() {
  return (
    <div className={styles.skeleton}>
      <div className={styles.skeletonHeader} />
      <div className={styles.skeletonBody}>
        <div className={styles.skeletonLine} style={{ width: "55%" }} />
        <div className={styles.skeletonLine} style={{ width: "40%" }} />
      </div>
      <div className={styles.skeletonBody}>
        <div className={styles.skeletonLine} style={{ width: "80%" }} />
        <div className={styles.skeletonLine} style={{ width: "65%" }} />
        <div className={styles.skeletonLine} style={{ width: "72%" }} />
      </div>
      <div className={styles.skeletonBody}>
        <div className={styles.skeletonLine} style={{ width: "90%" }} />
        <div className={styles.skeletonLine} style={{ width: "60%" }} />
      </div>
    </div>
  );
}

function TaskResultBlock({ result }: { result: TaskResult }) {
  return (
    <div className={result.status === "error" ? `${styles.taskBlock} ${styles.taskBlockError}` : styles.taskBlock}>
      <div className={styles.taskHeader}>
        <span className={styles.badge}>{result.tool}</span>
        <span className={styles.taskDescription}>{result.description}</span>
        {result.status === "ok" && (
          <span className={styles.taskCount}>{result.record_count} reg.</span>
        )}
      </div>
      {result.status === "error" && result.error && (
        <p className={styles.taskError}>{result.error}</p>
      )}
      {result.status === "ok" && result.records.length > 0 && (
        <DataRenderer records={result.records} />
      )}
    </div>
  );
}

export function ReceiptCard({ entry, index }: ReceiptCardProps) {
  const { question, response, status, error } = entry;
  const num = String(index).padStart(3, "0");

  return (
    <article className={styles.card}>

      {/* ── Card header bar ── */}
      <div className={styles.cardBar}>
        <span className={styles.cardBarLabel}>Recibo de consulta</span>
        <span className={styles.cardBarNum}>#{num}</span>
      </div>

      <div className={styles.cardBody}>

        {/* ── Section 1: original question (always visible) ── */}
        <section className={`${styles.section} ${styles.questionSection}`}>
          <SectionLabel>Pregunta original</SectionLabel>
          <div className={styles.questionBox}>
            <p className={styles.question}>{question}</p>
          </div>
        </section>

        {/* ── Loading ── */}
        {status === "loading" && <Skeleton />}

        {/* ── Error ── */}
        {status === "error" && (
          <section className={`${styles.section} ${styles.sectionError}`}>
            <SectionLabel>Error</SectionLabel>
            <p className={styles.errorText}>{error ?? "Error desconocido."}</p>
            <p className={styles.errorHint}>
              El backend no pudo procesar la solicitud. Intenta reformular la
              pregunta o verifica que los servicios estén activos.
            </p>
          </section>
        )}

        {/* ── Success ── */}
        {status === "success" && response && (
          <div className={styles.successLayout}>
            <section className={`${styles.section} ${styles.planSection}`}>
              <SectionLabel>Plan del agente</SectionLabel>
              <p className={styles.reasoning}>{response.plan.reasoning}</p>
              <ol className={styles.taskList}>
                {response.plan.tasks.map((task) => (
                  <li key={task.id} className={styles.taskItem}>
                    <span className={styles.badge}>{task.tool}</span>
                    <p className={styles.taskDescription}>{task.description}</p>
                  </li>
                ))}
              </ol>
            </section>

            <section className={`${styles.section} ${styles.resultsSection}`}>
              <SectionLabel>
                Resultados · {response.total_records} registro{response.total_records !== 1 ? "s" : ""} en total
              </SectionLabel>
              <div className={styles.taskResults}>
                {response.results.map((result) => (
                  <TaskResultBlock key={result.task_id} result={result} />
                ))}
              </div>
            </section>

            <section className={`${styles.section} ${styles.synthesisSection}`}>
              <SectionLabel>Síntesis</SectionLabel>
              <div className={styles.synthesisBody}>
                <SynthesisContent text={response.synthesis} />
              </div>
            </section>
          </div>
        )}

      </div>
    </article>
  );
}
