import { useEffect, useRef } from "react";

import styles from "./InlineMessageEditor.module.css";

export interface InlineMessageEditorProps {
  value: string;
  disabled?: boolean;
  onChange(value: string): void;
  onSave(): void;
  onCancel(): void;
}

export function InlineMessageEditor({
  value,
  disabled = false,
  onChange,
  onSave,
  onCancel,
}: InlineMessageEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const textarea = textareaRef.current;

    if (!textarea) {
      return;
    }

    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    resizeTextarea(textarea);
  }, []);

  return (
    <div className={styles.editor}>
      <textarea
        ref={textareaRef}
        className={styles.textarea}
        value={value}
        disabled={disabled}
        aria-label="编辑用户消息"
        rows={1}
        onChange={(event) => {
          onChange(event.target.value);
          resizeTextarea(event.target);
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            onCancel();
          }

          if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
            event.preventDefault();
            onSave();
          }
        }}
      />

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.cancelButton}
          disabled={disabled}
          onClick={onCancel}
        >
          取消
        </button>
        <button
          type="button"
          className={styles.saveButton}
          disabled={disabled || !value.trim()}
          onClick={onSave}
        >
          创建分支
        </button>
      </div>
    </div>
  );
}

function resizeTextarea(textarea: HTMLTextAreaElement): void {
  textarea.style.height = "auto";
  textarea.style.height = `${textarea.scrollHeight}px`;
}
