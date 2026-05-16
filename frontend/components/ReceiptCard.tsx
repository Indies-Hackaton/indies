"use client";

import { useId, useState } from "react";
import type { AuditResponse, QueryEntry, TaskResult } from "@/lib/types";
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

function AgentPlanSection({ plan }: { plan: AuditResponse["plan"] }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const taskCount = plan.tasks.length;

  return (
    <section className={`${styles.section} ${styles.planSection}`}>
      <div className={`${styles.planCard} ${open ? styles.planCardOpen : ""}`}>
        <button
          type="button"
          className={styles.planCardHeader}
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-controls={panelId}
        >
          <span className={styles.planCardHeaderMain}>
            <SectionLabel>Plan del agente</SectionLabel>
            <span className={styles.planCardMeta}>
              {taskCount} tarea{taskCount !== 1 ? "s" : ""} planificada
              {taskCount !== 1 ? "s" : ""}
            </span>
          </span>
          <span className={styles.planCardAction}>
            <span className={styles.planCardActionLabel}>
              {open ? "Ocultar" : "Ver detalle"}
            </span>
            <span
              className={`${styles.planCardChevron} ${open ? styles.planCardChevronOpen : ""}`}
              aria-hidden
            >
              ▾
            </span>
          </span>
        </button>

        <div id={panelId} className={styles.planCardBody} hidden={!open}>
          <p className={styles.planBodyLabel}>Razonamiento y tareas</p>
          <p className={styles.reasoning}>{plan.reasoning}</p>
          <ol className={styles.taskList}>
            {plan.tasks.map((task) => (
              <li key={task.id} className={styles.taskItem}>
                <span className={styles.badge}>{task.tool}</span>
                <p className={styles.taskDescription}>{task.description}</p>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
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

      <div className={styles.cardBar}>
        <span className={styles.cardBarLabel}>Recibo de consulta</span>
        <span className={styles.cardBarNum}>#{num}</span>
      </div>

      <div className={styles.cardBody}>

        <section className={`${styles.section} ${styles.questionSection}`}>
          <SectionLabel>Pregunta original</SectionLabel>
          <div className={styles.questionBox}>
            <p className={styles.question}>{question}</p>
          </div>
        </section>

        {status === "loading" && <Skeleton />}

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

        {status === "success" && response && (
          <div className={styles.successLayout}>
            <AgentPlanSection plan={response.plan} />

            <section className={`${styles.section} ${styles.resultsSection}`}>
              <SectionLabel>
                Resultados · {response.total_records} registro
                {response.total_records !== 1 ? "s" : ""} en total
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
