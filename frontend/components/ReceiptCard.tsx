import type { QueryEntry } from "@/lib/types";
import { DataRenderer } from "./DataRenderer";
import styles from "./ReceiptCard.module.css";

interface ReceiptCardProps {
  entry: QueryEntry;
  index: number;
}

function buildQueryString(tool: string, codigoorg: string | null, fecha: string | null): string {
  const base = "GET /servicios/v1/publico/ordenesdecompra.json";
  const params: string[] = ["ticket=••••••••"];
  if (codigoorg) params.push(`CodigoOrganismo=${codigoorg}`);
  if (fecha) params.push(`fecha=${fecha}`);
  return `${base}\n  ?${params.join("\n  &")}`;
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <p className={styles.sectionLabel}>{children}</p>;
}

function Skeleton() {
  return (
    <div className={styles.skeleton}>
      <div className={styles.skeletonHeader} />
      <div className={styles.skeletonBody}>
        <div className={styles.skeletonLine} style={{ width: "60%" }} />
        <div className={styles.skeletonLine} style={{ width: "40%" }} />
      </div>
      <div className={styles.skeletonBody}>
        <div className={styles.skeletonLine} style={{ width: "80%" }} />
        <div className={styles.skeletonLine} style={{ width: "55%" }} />
        <div className={styles.skeletonLine} style={{ width: "70%" }} />
      </div>
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
        <section className={styles.section}>
          <SectionLabel>Pregunta original</SectionLabel>
          <p className={styles.question}>{question}</p>
        </section>

        {/* ── Loading state ── */}
        {status === "loading" && <Skeleton />}

        {/* ── Error state ── */}
        {status === "error" && (
          <section className={`${styles.section} ${styles.sectionError}`}>
            <SectionLabel>Error</SectionLabel>
            <p className={styles.errorText}>{error ?? "Error desconocido."}</p>
            <p className={styles.errorHint}>
              El backend no pudo procesar la solicitud. Intenta reformular la pregunta o verifica que los servicios estén activos.
            </p>
          </section>
        )}

        {/* ── Unknown intent state ── */}
        {status === "unknown-intent" && response && (
          <>
            <section className={styles.section}>
              <SectionLabel>Interpretación del modelo</SectionLabel>
              <div className={styles.intentRow}>
                <span className={`${styles.badge} ${styles.badgeUnknown}`}>unknown</span>
              </div>
              {response.intent.reasoning && (
                <p className={styles.reasoning}>{response.intent.reasoning}</p>
              )}
            </section>
            <section className={`${styles.section} ${styles.sectionWarning}`}>
              <SectionLabel>No se pudo resolver la consulta</SectionLabel>
              <p className={styles.warningText}>
                {!response.intent.parameters.fecha && !response.intent.parameters.codigoorg
                  ? "No se detectó una fecha ni un organismo. Incluye al menos una fecha para continuar."
                  : !response.intent.parameters.fecha
                  ? "No se detectó una fecha. Incluye una fecha específica, por ejemplo: \"el 5 de febrero de 2024\"."
                  : "La consulta no pudo mapearse a una búsqueda conocida. Intenta ser más específico."}
              </p>
            </section>
          </>
        )}

        {/* ── Success state ── */}
        {status === "success" && response && (
          <>
            {/* Section 2: intent interpretation */}
            <section className={styles.section}>
              <SectionLabel>Interpretación del modelo</SectionLabel>
              <div className={styles.intentRow}>
                <span className={styles.badge}>{response.intent.tool}</span>
                {response.intent.parameters.codigoorg && (
                  <span className={styles.param}>
                    org: {response.intent.parameters.codigoorg}
                  </span>
                )}
                {response.intent.parameters.fecha && (
                  <span className={styles.param}>
                    fecha: {response.intent.parameters.fecha}
                  </span>
                )}
              </div>
              {response.intent.reasoning && (
                <p className={styles.reasoning}>{response.intent.reasoning}</p>
              )}
            </section>

            {/* Section 3: query sent */}
            <section className={styles.section}>
              <SectionLabel>Consulta enviada a Mercado Público</SectionLabel>
              <pre className={styles.queryBlock}>
                {buildQueryString(
                  response.intent.tool,
                  response.intent.parameters.codigoorg,
                  response.intent.parameters.fecha,
                )}
              </pre>
            </section>

            {/* Section 4: results */}
            <section className={styles.section}>
              <SectionLabel>Resultados</SectionLabel>
              {response.data ? (
                <DataRenderer data={response.data} />
              ) : (
                <p className={styles.noData}>
                  {response.detail ?? "Sin datos disponibles para esta consulta."}
                </p>
              )}
            </section>
          </>
        )}

      </div>
    </article>
  );
}
