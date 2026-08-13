import { useEffect, useRef, useState } from "react";
import { BookOpenText, Check, Info, X } from "lucide-react";

import styles from "./FactSetEditor.module.css";

export interface FactSetEditorProps {
  open: boolean;
  value: string;
  loading?: boolean;
  saving?: boolean;
  statusMessage?: string | null;
  onClose(): void;
  onSave(value: string): Promise<boolean>;
}

export function FactSetEditor({
  open,
  value,
  loading = false,
  saving = false,
  statusMessage = null,
  onClose,
  onSave,
}: FactSetEditorProps) {
  const [draft, setDraft] = useState(value);
  const [baseline, setBaseline] = useState(value);
  const [saved, setSaved] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    setDraft(value);
    setBaseline(value);
    setSaved(false);
    window.requestAnimationFrame(() => textareaRef.current?.focus());
  }, [open]);

  useEffect(() => {
    if (open && value !== baseline && draft === baseline) {
      setDraft(value);
      setBaseline(value);
    }
  }, [baseline, draft, open, value]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !saving) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose, saving]);

  const changed = draft !== baseline;
  const estimatedTokens = Math.ceil(draft.trim().length / 2.4);

  return (
    <div className={styles.root} data-open={open} aria-hidden={!open}>
      <button
        type="button"
        className={styles.backdrop}
        aria-label="关闭不变事实编辑器"
        tabIndex={open ? 0 : -1}
        onClick={() => {
          if (!saving) {
            onClose();
          }
        }}
      />

      <section
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="fact-set-title"
      >
        <header className={styles.header}>
          <span className={styles.icon} aria-hidden="true">
            <BookOpenText size={18} strokeWidth={1.8} />
          </span>
          <span className={styles.heading}>
            <span className={styles.eyebrow}>全局上下文</span>
            <h2 id="fact-set-title">不变事实</h2>
          </span>
          <button
            type="button"
            className={styles.closeButton}
            aria-label="关闭"
            disabled={saving}
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>

        <div className={styles.body}>
          <p className={styles.description}>
            写下长期有效的背景、偏好或规则。它独立于会话保存，并在每次请求开头只加入一次。
          </p>

          <div className={styles.note}>
            <Info size={15} aria-hidden="true" />
            <span>这里的内容不会进入聊天记录，也不会参与历史摘要。</span>
          </div>

          <label className={styles.editorLabel} htmlFor="fact-set-content">
            设定内容
          </label>
          <div className={styles.editor}>
            <textarea
              ref={textareaRef}
              id="fact-set-content"
              value={draft}
              disabled={loading || saving}
              spellCheck={false}
              placeholder={
                "例如：\n- 默认使用中文回答\n- 这是一个单人、本地运行的对话工具\n- 不替我做未经询问的产品决策"
              }
              onChange={(event) => {
                setDraft(event.target.value);
                setSaved(false);
              }}
            />
            <div className={styles.editorMeta}>
              <span>{draft.length.toLocaleString("zh-CN")} 字符</span>
              <span>约 {estimatedTokens.toLocaleString("zh-CN")} Token</span>
            </div>
          </div>
        </div>

        <footer className={styles.footer}>
          <span
            className={styles.saveState}
            data-visible={saved || loading || Boolean(statusMessage)}
            data-error={Boolean(statusMessage)}
          >
            {saved ? <Check size={14} aria-hidden="true" /> : null}
            {loading ? "正在读取…" : statusMessage || (saved ? "已保存" : "")}
          </span>
          <div className={styles.footerActions}>
            <button
              type="button"
              className={styles.cancelButton}
              disabled={saving}
              onClick={onClose}
            >
              取消
            </button>
            <button
              type="button"
              className={styles.saveButton}
              disabled={!changed || loading || saving}
              onClick={async () => {
                setSaved(false);
                const success = await onSave(draft);
                if (success) {
                  setBaseline(draft);
                  setSaved(true);
                }
              }}
            >
              {saving ? "保存中…" : "保存设定"}
            </button>
          </div>
        </footer>
      </section>
    </div>
  );
}
