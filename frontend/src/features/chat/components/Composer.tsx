import { useEffect, useRef, useState } from "react";
import { ArrowUp, Square } from "lucide-react";

import { IconButton } from "../../../shared/ui/IconButton";
import styles from "./Composer.module.css";

export interface ComposerProps {
  disabled?: boolean;
  generating?: boolean;
  stopping?: boolean;
  onSend(content: string): Promise<void>;
  onStop(): Promise<void>;
}

export function Composer({
  disabled = false,
  generating = false,
  stopping = false,
  onSend,
  onStop,
}: ComposerProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    resizeTextarea(textareaRef.current);
  }, [value]);

  const submit = async () => {
    const content = value.trim();

    if (!content || disabled || generating) {
      return;
    }

    setValue("");
    await onSend(content);
    textareaRef.current?.focus();
  };

  return (
    <div className={styles.composer}>
      <textarea
        ref={textareaRef}
        className={styles.textarea}
        value={value}
        disabled={disabled || generating}
        aria-label="输入消息"
        placeholder="询问任何问题"
        rows={1}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            void submit();
          }
        }}
      />

      {generating ? (
        <IconButton
          label={stopping ? "正在停止" : "停止生成"}
          tone="solid"
          className={styles.sendButton}
          disabled={stopping}
          onClick={() => void onStop()}
        >
          <Square size={13} fill="currentColor" strokeWidth={0} />
        </IconButton>
      ) : (
        <IconButton
          label="发送消息"
          tone="solid"
          className={styles.sendButton}
          disabled={disabled || !value.trim()}
          onClick={() => void submit()}
        >
          <ArrowUp size={18} strokeWidth={2.3} />
        </IconButton>
      )}
    </div>
  );
}

function resizeTextarea(textarea: HTMLTextAreaElement | null): void {
  if (!textarea) {
    return;
  }

  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
}
