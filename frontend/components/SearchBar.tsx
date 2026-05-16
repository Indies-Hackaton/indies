"use client";

import { useRef, useState, type KeyboardEvent, type FormEvent } from "react";
import styles from "./SearchBar.module.css";

interface SearchBarProps {
  onSubmit: (message: string) => void;
  disabled?: boolean;
}

export function SearchBar({ onSubmit, disabled = false }: SearchBarProps) {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  function handleSubmit(e?: FormEvent) {
    e?.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
    inputRef.current?.focus();
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") handleSubmit();
  }

  return (
    <div className={styles.wrapper}>
      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        <input
          ref={inputRef}
          className={styles.input}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Consulta en lenguaje natural…"
          disabled={disabled}
          autoComplete="off"
          spellCheck={false}
          aria-label="Consulta"
        />
        <button
          className={styles.button}
          type="submit"
          disabled={disabled || !value.trim()}
          aria-label="Enviar consulta"
        >
          {disabled ? (
            <span className={styles.spinner} aria-hidden="true" />
          ) : (
            "→"
          )}
        </button>
      </form>
    </div>
  );
}
