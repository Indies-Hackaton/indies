import styles from "./ExampleChips.module.css";

const EXAMPLES = [
  "Órdenes del organismo 7239 el 05 de febrero de 2024",
  "Órdenes del organismo 1234 el 12 de marzo de 2024",
  "Todas las órdenes de compra del 10 de enero de 2024",
  "Todas las órdenes de compra del 20 de abril de 2024",
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
