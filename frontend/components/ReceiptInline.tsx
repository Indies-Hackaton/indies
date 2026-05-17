"use client";

import { useState } from "react";
import type { ChatTurn } from "@/lib/types";
import styles from "./ReceiptInline.module.css";

interface ReceiptInlineProps {
  turn: ChatTurn;
  onOpenPanel: (turn: ChatTurn) => void;
}

export function ReceiptInline({ turn, onOpenPanel }: ReceiptInlineProps) {
  const [open, setOpen] = useState(false);
  const { planner, toolRuns, totalRecords } = turn;

  const taskCount = planner?.plan?.tasks?.length ?? 0;
  const errorCount = toolRuns.filter((tr) => tr.status === "error").length;

  return (
    <div className={styles.strip}>

      {/* ── Collapsed header ── */}
      <button
        className={styles.header}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className={styles.headerLeft}>
          <span className={styles.icon}>{open ? "▾" : "▸"}</span>
          <span className={styles.meta}>
            {taskCount} tarea{taskCount !== 1 ? "s" : ""}
          </span>
          <span className={styles.dot}>·</span>
          <span className={styles.meta}>
            {totalRecords} registro{totalRecords !== 1 ? "s" : ""}
          </span>
          {errorCount > 0 && (
            <>
              <span className={styles.dot}>·</span>
              <span className={styles.errorBadge}>
                {errorCount} error{errorCount !== 1 ? "es" : ""}
              </span>
            </>
          )}
        </span>
        <span className={styles.label}>Fuentes</span>
      </button>

      {/* ── Expanded body ── */}
      {open && (
        <div className={styles.body}>
          {planner?.plan && (
            <>
              <p className={styles.reasoning}>{planner.plan.reasoning}</p>
              <ul className={styles.taskList}>
                {planner.plan.tasks?.map((task) => {
                  const result = toolRuns.find((tr) => tr.task_id === task.id);
                  return (
                    <li key={task.id} className={styles.taskRow}>
                      <span className={styles.badge}>{task.tool}</span>
                      <span className={styles.taskDesc}>{task.description}</span>
                      {result && (
                        <span
                          className={
                            result.status === "error"
                              ? `${styles.taskCount} ${styles.taskCountError}`
                              : styles.taskCount
                          }
                        >
                          {result.status === "error"
                            ? "error"
                            : `${result.record_count} reg.`}
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </>
          )}

          <button
            className={styles.panelBtn}
            type="button"
            onClick={() => onOpenPanel(turn)}
          >
            Ver recibo completo →
          </button>
        </div>
      )}
    </div>
  );
}
