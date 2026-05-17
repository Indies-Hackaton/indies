"use client";

import { useMemo, useState } from "react";
import styles from "./DataRenderer.module.css";

interface DataRendererProps {
  records: Record<string, unknown>[];
  /** Más alto y ancho completo cuando va dentro de Fuentes en el chat. */
  variant?: "default" | "sources";
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
  senator: "Senador/a",
  staff_name: "Nombre",
  role: "Cargo",
  contract_type: "Tipo de contrato",
  amount_clp: "Monto (CLP)",
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

const SENATE_COLUMN_ORDER = [
  "staff_name",
  "role",
  "contract_type",
  "amount_clp",
  "senator",
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
  ...SENATE_COLUMN_ORDER,
];

const HIDDEN_COLUMNS = new Set(["raw"]);

const WRAP_COLUMNS = new Set([
  "Nombre",
  "name",
  "NombreOrganismo",
  "NombreProveedor",
  "senator",
  "staff_name",
  "role",
]);

const AMOUNT_COLUMNS = new Set([
  "amount_clp",
  "MontoNeto",
  "MontoBruto",
]);

function isSenateSchema(columns: string[]): boolean {
  return columns.includes("staff_name") && columns.includes("senator");
}

function stickyColumnKey(columns: string[]): string | null {
  if (columns.includes("staff_name")) return "staff_name";
  for (const key of CODE_COLUMNS) {
    if (columns.includes(key)) return key;
  }
  if (columns.includes("senator")) return null;
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
  if (isSenateSchema(visible)) {
    const ordered = SENATE_COLUMN_ORDER.filter((k) => visible.includes(k));
    for (const key of visible) {
      if (!ordered.includes(key)) ordered.push(key);
    }
    return ordered;
  }
  const ordered: string[] = [];
  for (const key of COLUMN_PRIORITY) {
    if (visible.includes(key)) ordered.push(key);
  }
  for (const key of visible) {
    if (!ordered.includes(key)) ordered.push(key);
  }
  return ordered;
}

function formatPersonName(value: string): string {
  if (!value.trim()) return value;
  return value
    .toLowerCase()
    .split(/\s+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatCurrency(value: number): string {
  return value.toLocaleString("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  });
}

function formatValue(value: unknown, column: string): string {
  if (value === null || value === undefined) return "—";
  if (column === "_source") {
    if (value === "tenders") return "Licitación";
    if (value === "purchase_orders") return "Orden de compra";
  }
  if (AMOUNT_COLUMNS.has(column)) {
    const amount =
      typeof value === "number" ? value : Number(String(value).replace(/\./g, ""));
    if (!Number.isNaN(amount)) return formatCurrency(amount);
  }
  if (column === "senator" || column === "staff_name") {
    return formatPersonName(String(value));
  }
  if (typeof value === "number") {
    if (Number.isInteger(value) && value > 999 && column.toLowerCase().includes("monto")) {
      return formatCurrency(value);
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
  if (WRAP_COLUMNS.has(column)) classes.push(styles.cellWrap);
  if (AMOUNT_COLUMNS.has(column)) classes.push(styles.cellAmount);
  if (column === "_source") classes.push(styles.cellSource);
  return classes.length > 0 ? classes.join(" ") : undefined;
}

export function DataRenderer({ records, variant = "default" }: DataRendererProps) {
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

  const isWideTable =
    columns.length > 4 || (isSenateSchema(columns) && columns.length >= 4);

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
      <div
        className={
          variant === "sources" ? `${styles.scroll} ${styles.scrollSources}` : styles.scroll
        }
      >
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
