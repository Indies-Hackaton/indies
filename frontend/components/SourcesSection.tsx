"use client";

import { useState } from "react";
import type { ToolRunOut } from "@/lib/types";
import { DataRenderer } from "./DataRenderer";
import styles from "./SourcesSection.module.css";

// ── Source row ────────────────────────────────────────────────────

interface SourceRowProps {
  run: ToolRunOut;
  index: number;
  id: string;
}

function buildApiCall(run: ToolRunOut): string {
  const params = Object.entries(run.parameters)
    .map(([k, v]) => `${k}=${v}`)
    .join(" · ");
  return params ? `${run.tool}\n${params}` : run.tool;
}

function SourceRow({ run, index, id }: SourceRowProps) {
  const isEmpty = run.record_count === 0;
  const [open, setOpen] = useState(false);

  return (
    <div
      id={id}
      className={`${styles.row} ${isEmpty ? styles.rowEmpty : ""} ${open ? styles.rowOpen : ""}`}
    >
      <button
        className={styles.rowHeader}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className={`${styles.index} ${isEmpty ? styles.indexEmpty : ""}`}>
          [{index}]
        </span>
        <span className={styles.toolName}>{run.tool}</span>
        <span className={`${styles.count} ${isEmpty ? styles.countEmpty : ""}`}>
          {isEmpty ? "sin registros" : `${run.record_count} reg.`}
        </span>
        <span className={styles.chevron} aria-hidden="true">
          {open ? "▾" : "▸"}
        </span>
      </button>

      {open && (
        <div className={styles.rowBody}>
          {run.status === "error" ? (
            <p className={styles.rowError}>{run.error ?? "Error al ejecutar esta consulta."}</p>
          ) : (
            <>
              <pre className={styles.apiCall}>{buildApiCall(run)}</pre>
              {run.result.records.length > 0 ? (
                <DataRenderer records={run.result.records} />
              ) : (
                <p className={styles.noData}>Esta consulta no retornó registros.</p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── Sources section ───────────────────────────────────────────────

interface SourcesSectionProps {
  toolRuns: ToolRunOut[];
  totalRecords: number;
  messageId: string;
}

export function SourcesSection({ toolRuns, totalRecords, messageId }: SourcesSectionProps) {
  const [open, setOpen] = useState(true);

  if (toolRuns.length === 0) return null;

  const sourceCount = toolRuns.length;

  return (
    <div className={styles.section}>
      {/* ── Collapsible header ── */}
      <button
        className={styles.header}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className={styles.headerLeft}>
          <span className={styles.chevron} aria-hidden="true">
            {open ? "▾" : "▸"}
          </span>
          <span className={styles.label}>Fuentes</span>
        </span>
        <span className={styles.headerMeta}>
          {sourceCount} fuente{sourceCount !== 1 ? "s" : ""}
          {" · "}
          {totalRecords} registro{totalRecords !== 1 ? "s" : ""}
        </span>
      </button>

      {/* ── Source rows ── */}
      {open && (
        <div className={styles.body}>
          {toolRuns.map((run, i) => (
            <SourceRow
              key={run.id}
              run={run}
              index={i + 1}
              id={`source-${messageId}-${i + 1}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
