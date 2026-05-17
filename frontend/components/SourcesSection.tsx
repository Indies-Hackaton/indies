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
  activeTick: number;
}

function buildApiCall(run: ToolRunOut): string {
  const params = Object.entries(run.parameters)
    .map(([k, v]) => `${k}=${v}`)
    .join(" · ");
  return params ? `${run.tool}\n${params}` : run.tool;
}

function SourceRow({ run, index, id, isActive, activeTick }: SourceRowProps) {
  const isEmpty = run.record_count === 0;
  const [open, setOpen] = useState(false);
  const rowRef = useRef<HTMLDivElement>(null);

  // Re-run whenever isActive becomes true OR when the same marker is clicked
  // again (activeTick increments). setTimeout gives React time to render the
  // newly-opened section before scrollIntoView fires.
  useEffect(() => {
    if (!isActive) return;
    setOpen(true);
    const timer = setTimeout(() => {
      rowRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }, 60);
    return () => clearTimeout(timer);
  }, [isActive, activeTick]);

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
                <DataRenderer records={run.result.records} variant="sources" />
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
  activeTick: number;
  /** Progressive reveal: only show the first N tool runs. Defaults to all. */
  maxVisible?: number;
}

export function SourcesSection({
  toolRuns,
  totalRecords,
  messageId,
  activeIndex,
  activeTick,
  maxVisible,
}: SourcesSectionProps) {
  const visibleRuns = maxVisible !== undefined
    ? toolRuns.slice(0, maxVisible)
    : toolRuns;
  const [open, setOpen] = useState(true);

  // Force section open when a citation marker activates a row.
  useEffect(() => {
    if (activeIndex !== null) setOpen(true);
  }, [activeIndex, activeTick]);

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
          {visibleRuns.map((run, i) => (
            <SourceRow
              key={run.id}
              run={run}
              index={i + 1}
              id={`source-${messageId}-${i + 1}`}
              isActive={activeIndex === i + 1}
              activeTick={activeTick}
            />
          ))}
        </div>
      )}
    </div>
  );
}
