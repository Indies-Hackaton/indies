"use client";

import { useMemo, useState } from "react";
import styles from "./DataRenderer.module.css";

interface DataRendererProps {
  records: Record<string, unknown>[];
}

const COLUMN_LABELS: Record<string, string> = {
  CodigoOrdenCompra: "Código OC",
  CodigoExterno: "Cód. licitación",
  Codigo: "Código",
  CodigoLicitacion: "Cód. licitación",
  Nombre: "Nombre / descripción",
  NombreOrganismo: "Organismo",
  CodigoOrganismo: "Cód. org.",
  code: "Código",
  name: "Nombre",
  match_type: "Coincidencia",
  MontoBruto: "Monto bruto",
  MontoNeto: "Monto neto",
  FechaCreacion: "Fecha creación",
  FechaCierre: "Fecha cierre",
  CodigoEstado: "Estado",
  Estado: "Estado",
  _source: "Fuente",
  _query_fecha: "Fecha consulta",
  NombreProveedor: "Proveedor",
};

/** Código de licitación / OC primero — columna fija al hacer scroll horizontal. */
const CODE_COLUMNS = [
  "CodigoExterno",
  "Codigo",
  "CodigoOrdenCompra",
  "CodigoLicitacion",
  "code",
  "CodigoOrganismo",
];

const COLUMN_PRIORITY = [
  ...CODE_COLUMNS,
  "_source",
  "_query_fecha",
  "Nombre",
  "name",
  "CodigoEstado",
  "Estado",
  "FechaCierre",
  "FechaCreacion",
  "match_type",
  "MontoNeto",
  "MontoBruto",
  "NombreProveedor",
  "NombreOrganismo",
];

const HIDDEN_COLUMNS = new Set(["raw"]);

const WRAP_COLUMNS = new Set([
  "Nombre",
  "name",
  "NombreOrganismo",
  "NombreProveedor",
]);

function stickyColumnKey(columns: string[]): string | null {
  for (const key of CODE_COLUMNS) {
    if (columns.includes(key)) return key;
  }
  return columns[0] ?? null;
}

function isCodeColumn(column: string): boolean {
  return CODE_COLUMNS.includes(column);
}

function labelFor(key: string): string {
  return COLUMN_LABELS[key] ?? key;
}

function orderColumns(keys: string[]): string[] {
  const visible = keys.filter((k) => !HIDDEN_COLUMNS.has(k));
  const ordered: string[] = [];
  for (const key of COLUMN_PRIORITY) {
    if (visible.includes(key)) ordered.push(key);
  }
  for (const key of visible) {
    if (!ordered.includes(key)) ordered.push(key);
  }
  return ordered;
}

function formatValue(value: unknown, column: string): string {
  if (value === null || value === undefined) return "—";
  if (column === "_source") {
    if (value === "tenders") return "Licitación";
    if (value === "purchase_orders") return "Orden de compra";
  }
  if (typeof value === "number") {
    if (Number.isInteger(value) && value > 999 && column.toLowerCase().includes("monto")) {
      return value.toLocaleString("es-CL", {
        style: "currency",
        currency: "CLP",
        maximumFractionDigits: 0,
      });
    }
    return value.toLocaleString("es-CL");
  }
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (typeof value === "object") {
    const text = JSON.stringify(value);
    return text.length > 80 ? `${text.slice(0, 77)}…` : text;
  }
  return String(value);
}

function cellClass(column: string, stickyKey: string | null): string | undefined {
  const classes: string[] = [];
  if (column === stickyKey) classes.push(styles.cellSticky);
  else if (isCodeColumn(column)) classes.push(styles.cellCode);
  else if (WRAP_COLUMNS.has(column)) classes.push(styles.cellWrap);
  if (column === "_source") classes.push(styles.cellSource);
  return classes.length > 0 ? classes.join(" ") : undefined;
}

export function DataRenderer({ records }: DataRendererProps) {
  const [expanded, setExpanded] = useState(false);

  const columns = useMemo(
    () => (records.length > 0 ? orderColumns(Object.keys(records[0])) : []),
    [records]
  );

  const pinnedColumn = useMemo(
    () => stickyColumnKey(columns),
    [columns]
  );

  if (records.length === 0) {
    return <p className={styles.empty}>Sin registros para esta consulta.</p>;
  }

  const isWideTable = columns.length > 4;

  return (
    <div className={styles.tableWrap}>
      <div className={styles.tableMeta}>
        <p className={styles.count}>
          {records.length} registro{records.length !== 1 ? "s" : ""}
        </p>
        {isWideTable && (
          <p className={styles.scrollHint}>
            Desliza horizontalmente para ver todas las columnas
          </p>
        )}
      </div>
      <div className={styles.scroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col} className={cellClass(col, pinnedColumn)}>
                  {labelFor(col)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {records.map((row, i) => (
              <tr key={i}>
                {columns.map((col) => (
                  <td key={col} className={cellClass(col, pinnedColumn)}>
                    {formatValue(row[col], col)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className={styles.jsonWrap}>
        <button
          className={styles.jsonToggle}
          onClick={() => setExpanded((v) => !v)}
          type="button"
          aria-expanded={expanded}
        >
          <span className={styles.jsonToggleArrow}>{expanded ? "▾" : "▸"}</span>
          Datos en bruto
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
