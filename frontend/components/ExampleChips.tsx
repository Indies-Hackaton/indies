import styles from "./ExampleChips.module.css";

const EXAMPLES = [
  "Sueldos de los asesores del Senador Ossandón en el mes de abril del 2026",
  "Comparativa de los sueldos de todos los asesores para el cargo de Jefe de Gabinete en abril del 2026, indicando a cuál senador corresponde cada uno.",
  "Órdenes de compra de la Municipalidad de Maipú del 12 de marzo de 2026",
];

interface ExampleChipsProps {
  onSelect: (message: string) => void;
}

export function ExampleChips({ onSelect }: ExampleChipsProps) {
  return (
    <div className={styles.wrapper}>
      <p className={styles.label}>Ejemplos de consulta</p>
      <ul className={styles.list} role="list">
        {EXAMPLES.map((example) => (
          <li key={example}>
            <button
              className={styles.chip}
              onClick={() => onSelect(example)}
              type="button"
            >
              <span className={styles.arrow}>→</span>
              {example}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
