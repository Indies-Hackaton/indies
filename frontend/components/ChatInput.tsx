"use client";

import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import styles from "./ChatInput.module.css";

interface ChatInputProps {
  onSubmit: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSubmit, disabled = false }: ChatInputProps) {
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
    if (e.key === "Enter" && !e.shiftKey) handleSubmit();
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
          placeholder="Escribe tu consulta…"
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
