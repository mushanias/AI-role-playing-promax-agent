import { useEffect, useState } from "react";
import { Check, Copy, Pencil } from "lucide-react";

import { IconButton } from "../../../shared/ui/IconButton";
import type { ConversationTurn } from "../model/types";
import { formatDuration } from "../utils/formatDuration";
import { BranchNavigator } from "./BranchNavigator";
import { InlineMessageEditor } from "./InlineMessageEditor";
import styles from "./MessageTurn.module.css";

export interface MessageTurnProps {
  turn: ConversationTurn;
  isEditing: boolean;
  editingContent: string;
  disabled?: boolean;
  onStartEdit(): void;
  onEditingContentChange(content: string): void;
  onSaveEdit(): void;
  onCancelEdit(): void;
  onSelectVariant(direction: -1 | 1): void;
}

type CopiedTarget = "user" | "assistant" | null;

export function MessageTurn({
  turn,
  isEditing,
  editingContent,
  disabled = false,
  onStartEdit,
  onEditingContentChange,
  onSaveEdit,
  onCancelEdit,
  onSelectVariant,
}: MessageTurnProps) {
  const [copiedTarget, setCopiedTarget] = useState<CopiedTarget>(null);

  useEffect(() => {
    if (!copiedTarget) {
      return;
    }

    const timer = window.setTimeout(() => setCopiedTarget(null), 1300);
    return () => window.clearTimeout(timer);
  }, [copiedTarget]);

  const copyText = async (text: string, target: CopiedTarget) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedTarget(target);
    } catch {
      setCopiedTarget(null);
    }
  };

  return (
    <article className={styles.turn}>
      <section className={styles.userSection} aria-label="用户消息">
        {isEditing ? (
          <InlineMessageEditor
            value={editingContent}
            disabled={disabled}
            onChange={onEditingContentChange}
            onSave={onSaveEdit}
            onCancel={onCancelEdit}
          />
        ) : (
          <>
            <div className={styles.userBubble}>{turn.userContent}</div>
            <div className={styles.userToolbar}>
              <div className={styles.messageActions}>
                <IconButton
                  label={copiedTarget === "user" ? "已复制" : "复制用户消息"}
                  onClick={() => copyText(turn.userContent, "user")}
                >
                  {copiedTarget === "user" ? (
                    <Check size={15} />
                  ) : (
                    <Copy size={15} />
                  )}
                </IconButton>
                <IconButton
                  label="编辑用户消息"
                  disabled={disabled}
                  onClick={onStartEdit}
                >
                  <Pencil size={15} />
                </IconButton>
              </div>

              <BranchNavigator
                current={turn.variantIndex}
                total={turn.variantCount}
                disabled={disabled}
                onPrevious={() => onSelectVariant(-1)}
                onNext={() => onSelectVariant(1)}
              />
            </div>
          </>
        )}
      </section>

      <section className={styles.assistantSection} aria-label="助手回答">
        {turn.status === "pending" ? (
          <div className={styles.thinking} aria-label="正在生成回答">
            <span />
            <span />
            <span />
          </div>
        ) : (
          <div className={styles.assistantContent}>
            {turn.assistantContent
              ?.split("\n\n")
              .map((paragraph, index) => <p key={index}>{paragraph}</p>)}
          </div>
        )}

        {turn.assistantContent && turn.status === "completed" ? (
          <div className={styles.assistantFooter}>
            {turn.responseDurationMs != null ? (
              <span className={styles.responseTime}>
                生成用时 {formatDuration(turn.responseDurationMs)}
              </span>
            ) : null}
            <div className={styles.assistantToolbar}>
              <IconButton
                label={
                  copiedTarget === "assistant" ? "已复制" : "复制助手回答"
                }
                onClick={() =>
                  copyText(turn.assistantContent ?? "", "assistant")
                }
              >
                {copiedTarget === "assistant" ? (
                  <Check size={15} />
                ) : (
                  <Copy size={15} />
                )}
              </IconButton>
            </div>
          </div>
        ) : null}
      </section>
    </article>
  );
}
