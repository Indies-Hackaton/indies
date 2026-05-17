"use client";

import React from "react";
import type { Theme } from "@/hooks/useTheme";
import styles from "./ThemeToggle.module.css";

interface ThemeToggleProps {
  theme: Theme;
  onChange: (theme: Theme) => void;
}

function SunIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function SystemIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </svg>
  );
}

const OPTIONS: { value: Theme; label: string; Icon: () => React.ReactElement }[] = [
  { value: "light",  label: "Modo claro",    Icon: SunIcon },
  { value: "system", label: "Modo del sistema", Icon: SystemIcon },
  { value: "dark",   label: "Modo oscuro",   Icon: MoonIcon },
];

export function ThemeToggle({ theme, onChange }: ThemeToggleProps) {
  return (
    <div className={styles.toggle} role="group" aria-label="Tema de la interfaz">
      {OPTIONS.map(({ value, label, Icon }) => (
        <button
          key={value}
          className={`${styles.btn} ${theme === value ? styles.btnActive : ""}`}
          type="button"
          onClick={() => onChange(value)}
          aria-label={label}
          aria-pressed={theme === value}
          title={label}
        >
          <Icon />
        </button>
      ))}
    </div>
  );
}
