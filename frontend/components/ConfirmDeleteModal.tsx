"use client";

import { useEffect, useRef } from "react";
import styles from "./ConfirmDeleteModal.module.css";

interface ConfirmDeleteModalProps {
  title: string;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export function ConfirmDeleteModal({
  title,
  onConfirm,
  onCancel,
  isLoading = false,
}: ConfirmDeleteModalProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  // Focus the cancel button on open — safest default for a destructive action.
  useEffect(() => {
    cancelRef.current?.focus();
  }, []);

  // Close on Escape.
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onCancel]);

  return (
    <div
      className={styles.backdrop}
      onClick={onCancel}
      role="presentation"
    >
      <div
        className={styles.modal}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="delete-modal-title"
        aria-describedby="delete-modal-desc"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className={styles.heading} id="delete-modal-title">
          Eliminar conversación
        </h2>
        <p className={styles.description} id="delete-modal-desc">
          La conversación{" "}
          <span className={styles.convTitle}>&ldquo;{title}&rdquo;</span>{" "}
          se eliminará de forma permanente. No se puede deshacer.
        </p>

        <div className={styles.actions}>
          <button
            ref={cancelRef}
            className={styles.cancelBtn}
            type="button"
            onClick={onCancel}
            disabled={isLoading}
          >
            Cancelar
          </button>
          <button
            className={styles.confirmBtn}
            type="button"
            onClick={onConfirm}
            disabled={isLoading}
          >
            {isLoading ? (
              <span className={styles.spinner} aria-hidden="true" />
            ) : null}
            Eliminar
          </button>
        </div>
      </div>
    </div>
  );
}
