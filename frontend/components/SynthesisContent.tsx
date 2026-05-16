import styles from "./SynthesisContent.module.css";

interface SynthesisContentProps {
  text: string;
}

function renderInline(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

function parseBlocks(text: string): React.ReactNode[] {
  const blocks = text.trim().split(/\n\n+/);
  const nodes: React.ReactNode[] = [];

  blocks.forEach((block, blockIndex) => {
    const lines = block.split("\n").map((l) => l.trim()).filter(Boolean);
    if (lines.length === 0) return;

    const first = lines[0];
    if (first.startsWith("### ")) {
      nodes.push(
        <h3 key={blockIndex} className={styles.h3}>
          {renderInline(first.slice(4))}
        </h3>
      );
      lines.slice(1).forEach((line, i) => {
        if (line.startsWith("- ")) {
          nodes.push(
            <ul key={`${blockIndex}-ul-${i}`} className={styles.list}>
              <li>{renderInline(line.slice(2))}</li>
            </ul>
          );
        } else {
          nodes.push(
            <p key={`${blockIndex}-p-${i}`} className={styles.p}>
              {renderInline(line)}
            </p>
          );
        }
      });
      return;
    }

    if (first.startsWith("## ")) {
      nodes.push(
        <h2 key={blockIndex} className={styles.h2}>
          {renderInline(first.slice(3))}
        </h2>
      );
      const rest = lines.slice(1);
      if (rest.length > 0 && rest.every((l) => l.startsWith("- "))) {
        nodes.push(
          <ul key={`${blockIndex}-ul`} className={styles.list}>
            {rest.map((line, i) => (
              <li key={i}>{renderInline(line.slice(2))}</li>
            ))}
          </ul>
        );
      } else {
        rest.forEach((line, i) => {
          nodes.push(
            <p key={`${blockIndex}-p-${i}`} className={styles.p}>
              {renderInline(line)}
            </p>
          );
        });
      }
      return;
    }

    if (lines.every((l) => l.startsWith("- "))) {
      nodes.push(
        <ul key={blockIndex} className={styles.list}>
          {lines.map((line, i) => (
            <li key={i}>{renderInline(line.slice(2))}</li>
          ))}
        </ul>
      );
      return;
    }

    nodes.push(
      <p key={blockIndex} className={styles.p}>
        {lines.map((line, i) => (
          <span key={i}>
            {i > 0 && <br />}
            {renderInline(line)}
          </span>
        ))}
      </p>
    );
  });

  return nodes;
}

export function SynthesisContent({ text }: SynthesisContentProps) {
  return <div className={styles.root}>{parseBlocks(text)}</div>;
}
