"use client";

import { useState } from "react";
import styles from "./BrandLogo.module.css";

/** PNG en `frontend/public/brand/logo.png` */
export const BRAND_LOGO_PATH = "/brand/logo.png";

type BrandLogoMode = "full" | "icon" | "text";

interface BrandLogoProps {
  /** full: icono + nombre (header); icon: solo marca (avatar); text: solo texto */
  mode?: BrandLogoMode;
  size?: "sm" | "md";
  className?: string;
}

function TextName({
  size = "md",
  className,
}: {
  size?: "sm" | "md";
  className?: string;
}) {
  return (
    <span
      className={[styles.name, styles[size], className].filter(Boolean).join(" ")}
    >
      <span className={styles.word}>Transparenc</span>
      <span className={styles.ia}>IA</span>
    </span>
  );
}

function BrandMark({
  size,
  className,
  onError,
}: {
  size: "sm" | "md";
  className?: string;
  onError: () => void;
}) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={BRAND_LOGO_PATH}
      alt=""
      className={[styles.mark, styles[`mark_${size}`], className].filter(Boolean).join(" ")}
      onError={onError}
    />
  );
}

export function BrandLogo({
  mode = "full",
  size = "md",
  className,
}: BrandLogoProps) {
  const [imgFailed, setImgFailed] = useState(false);
  const rootClass = [styles.root, styles[size], styles[mode], className]
    .filter(Boolean)
    .join(" ");

  if (mode === "text" || (imgFailed && mode !== "icon")) {
    return (
      <span className={rootClass} aria-label="TransparencIA">
        <TextName size={size} />
      </span>
    );
  }

  if (mode === "icon") {
    return (
      <span className={rootClass} aria-label="TransparencIA">
        {!imgFailed ? (
          <BrandMark size={size} onError={() => setImgFailed(true)} />
        ) : (
          <span className={styles.iconFallback}>IA</span>
        )}
      </span>
    );
  }

  return (
    <span className={rootClass} aria-label="TransparencIA">
      {!imgFailed && (
        <BrandMark size={size} onError={() => setImgFailed(true)} />
      )}
      <TextName size={size} />
    </span>
  );
}
