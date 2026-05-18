import { SignIn } from "@clerk/nextjs";
import styles from "./page.module.css";

export default function SignInPage() {
  return (
    <div className={styles.page}>
      <div className={styles.brand}>
        <span className={styles.logo}>
          Vig<span className={styles.logoAccent}>IA</span>
        </span>
        <p className={styles.tagline}>
          Transparencia en datos públicos de Chile
        </p>
      </div>

      <SignIn />

      <p className={styles.note}>
        Inicia sesión para guardar y acceder a tu historial de consultas.
        <br />
        Puedes usar VigIA sin cuenta — tu historial no se guardará.
      </p>
    </div>
  );
}
