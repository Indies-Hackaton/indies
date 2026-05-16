"use client";

import { useState } from "react";
import styles from "./DataRenderer.module.css";

interface DataRendererProps {
  data: Record<string, unknown>;
}

// Keys the Mercado Público API commonly uses to wrap the record list.
// TODO: once a real API response is available, pin this to the exact key
// (e.g. replace the whole list with just ["Listado"]) and remove the
// generic array-scan fallback below. Tracking issue: check OVERVIEW.md
// under "MercadoPublicoClient" for the confirmed response shape.
const LIST_KEYS = ["Listado", "listado", "items", "data", "results"];

function extractList(data: Record<string, unknown>): Record<string, unknown>[] | null {
  for (const key of LIST_KEYS) {
    const value = data[key];
    if (Array.isArray(value) && value.length > 0) return value as Record<string, unknown>[];
  }
  // Fallback: find any top-level key that holds a non-empty array.
  // TODO: remove this fallback once the real response shape is confirmed —
  // it could accidentally pick up the wrong array in a more complex response.
  for (const value of Object.values(data)) {
    if (Array.isArray(value) && value.length > 0) return value as Record<string, unknown>[];
  }
  return null;
}

// TODO: replace this value-based heuristic with a column-name allowlist once
// the real API field names are confirmed. The right approach is:
//   const MONETARY_FIELDS = new Set(["MontoBruto", "MontoNeto", "MontoTotal", ...]);
//   if (MONETARY_FIELDS.has(columnKey)) → format as CLP currency.
// Pass `columnKey` into formatValue and remove the >999 number check entirely.
function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    // Heuristic: large integers are likely monetary amounts.
    // Fragile — will mis-format non-monetary large numbers (e.g. org codes).
    if (Number.isInteger(value) && value > 999) {
      return value.toLocaleString("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 });
    }
    return value.toLocaleString("es-CL");
  }
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

// Some column names from the API are verbose — shorten them for display.
const COLUMN_LABELS: Record<string, string> = {
  CodigoOrdenCompra:   "Código OC",
  NombreOrganismo:     "Organismo",
  CodigoOrganismo:     "Cód. Org.",
  MontoBruto:          "Monto bruto",
  MontoNeto:           "Monto neto",
  FechaCreacion:       "Fecha creación",
  FechaCierre:         "Fecha cierre",
  Nombre:              "Nombre",
  Estado:              "Estado",
  TipoMoneda:          "Moneda",
};

function labelFor(key: string): string {
  return COLUMN_LABELS[key] ?? key;
}

function TableRenderer({ rows }: { rows: Record<string, unknown>[] }) {
  const columns = Object.keys(rows[0]);

  return (
    <div className={styles.tableWrap}>
      <p className={styles.count}>{rows.length} registro{rows.length !== 1 ? "s" : ""}</p>
      <div className={styles.scroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col}>{labelFor(col)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                {columns.map((col) => (
                  <td key={col}>{formatValue(row[col])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function JsonRenderer({ data }: { data: Record<string, unknown> }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={styles.jsonWrap}>
      <button
        className={styles.jsonToggle}
        onClick={() => setExpanded((v) => !v)}
        type="button"
        aria-expanded={expanded}
      >
        <span className={styles.jsonToggleArrow}>{expanded ? "▾" : "▸"}</span>
        Respuesta sin formato
        <span className={styles.jsonToggleHint}>
          {expanded ? "ocultar" : "mostrar JSON"}
        </span>
      </button>
      {expanded && (
        <pre className={styles.json}>
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}

export function DataRenderer({ data }: DataRendererProps) {
  const list = extractList(data);

  if (list) return <TableRenderer rows={list} />;
  return <JsonRenderer data={data} />;
}
