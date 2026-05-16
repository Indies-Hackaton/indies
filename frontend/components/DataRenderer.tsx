"use client";

import { useState } from "react";
import styles from "./DataRenderer.module.css";

interface DataRendererProps {
  records: Record<string, unknown>[];
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
      return value.toLocaleString("es-CL", {
        style: "currency",
        currency: "CLP",
        maximumFractionDigits: 0,
      });
    }
    return value.toLocaleString("es-CL");
  }
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

// Some column names from the API are verbose — shorten them for display.
const COLUMN_LABELS: Record<string, string> = {
  CodigoOrdenCompra:    "Código OC",
  CodigoLicitacion:     "Código Licitación",
  NombreOrganismo:      "Organismo",
  CodigoOrganismo:      "Cód. Org.",
  MontoBruto:           "Monto bruto",
  MontoNeto:            "Monto neto",
  FechaCreacion:        "Fecha creación",
  FechaCierre:          "Fecha cierre",
  Nombre:               "Nombre",
  Estado:               "Estado",
  TipoMoneda:           "Moneda",
  NombreProveedor:      "Proveedor",
  CodigoProveedor:      "Cód. Proveedor",
};

function labelFor(key: string): string {
  return COLUMN_LABELS[key] ?? key;
}

export function DataRenderer({ records }: DataRendererProps) {
  const [expanded, setExpanded] = useState(false);

  if (records.length === 0) {
    return <p className={styles.empty}>Sin registros para esta consulta.</p>;
  }

  const columns = Object.keys(records[0]);

  return (
    <div className={styles.tableWrap}>
      <p className={styles.count}>
        {records.length} registro{records.length !== 1 ? "s" : ""}
      </p>
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
            {records.map((row, i) => (
              <tr key={i}>
                {columns.map((col) => (
                  <td key={col}>{formatValue(row[col])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Raw JSON toggle for debugging */}
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
            {JSON.stringify(records, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
