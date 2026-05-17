"use client";

import { useEffect, useRef, useState } from "react";
import type { ToolRunOut } from "@/lib/types";
import { DataRenderer } from "./DataRenderer";
import styles from "./SourcesSection.module.css";

// ── Source row ────────────────────────────────────────────────────

interface SourceRowProps {
  run: ToolRunOut;
  index: number;
  id: string;
  isActive: boolean;
}

function buildApiCall(run: ToolRunOut): string {
  const params = Object.entries(run.parameters)
    .map(([k, v]) => `${k}=${v}`)
    .join(" · ");
  return params ? `${run.tool}\n${params}` : run.tool;
}

function SourceRow({ run, index, id, isActive }: SourceRowProps) {
  const isEmpty = run.record_count === 0;
  const [open, setOpen] = useState(false);
  const rowRef = useRef<HTMLDivElement>(null);

  // Auto-expand and scroll when activated by a citation marker click.
  useEffect(() => {
    if (!isActive) return;
    setOpen(true);
    rowRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [isActive]);

  return (
    <div
      ref={rowRef}
      id={id}
      className={[
        styles.row,
        isEmpty ? styles.rowEmpty : "",
        open ? styles.rowOpen : "",
        isActive ? styles.rowActive : "",
      ].filter(Boolean).join(" ")}
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
  activeIndex: number | null;
}

export function SourcesSection({
  toolRuns,
  totalRecords,
  messageId,
  activeIndex,
}: SourcesSectionProps) {
  const [open, setOpen] = useState(true);

  // Force section open when a citation marker activates a row.
  useEffect(() => {
    if (activeIndex !== null) setOpen(true);
  }, [activeIndex]);

  if (toolRuns.length === 0) return null;

  const sourceCount = toolRuns.length;

  return (
    <div className={styles.section}>
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

      {open && (
        <div className={styles.body}>
          {toolRuns.map((run, i) => (
            <SourceRow
              key={run.id}
              run={run}
              index={i + 1}
              id={`source-${messageId}-${i + 1}`}
              isActive={activeIndex === i + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
