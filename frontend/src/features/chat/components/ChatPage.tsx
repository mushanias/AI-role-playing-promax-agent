import { useRef, useState } from "react";
import { PanelLeftOpen } from "lucide-react";

import { IconButton } from "../../../shared/ui/IconButton";
import type { ConversationController } from "../hooks/useConversationController";
import { createPreviewError } from "../services/errorPresentation";
import { Composer } from "./Composer";
import { ErrorNotice } from "./ErrorNotice";
import { MessageTurn } from "./MessageTurn";
import { PendingResponse } from "./PendingResponse";
import styles from "./ChatPage.module.css";

export interface ChatPageProps {
  controller: ConversationController;
  sidebarOpen: boolean;
  onOpenSidebar(): void;
}

export function ChatPage({
  controller,
  sidebarOpen,
  onOpenSidebar,
}: ChatPageProps) {
  const {
    view,
    isLoading,
    isSubmitting,
    isGenerating,
    error,
    pendingRequest,
    failedRequestContent,
    editingTurnId,
    editingContent,
    startEditing,
    changeEditingContent,
    saveEditing,
    cancelEditing,
    selectVariant,
    sendMessage,
    stopGeneration,
    refresh,
    dismissError,
  } = controller;
  const [previewMode, setPreviewMode] = useState(readPreviewMode);
  const previewStartedAt = useRef(Date.now()).current;
  const simulatedError = createPreviewError(previewMode);
  const displayedError = error ?? simulatedError;
  const currentPendingRequest =
    pendingRequest?.conversationId === view?.conversationId
      ? pendingRequest
      : null;
  const displayedPendingRequest =
    currentPendingRequest ??
    (previewMode === "waiting"
      ? {
          conversationId: view?.conversationId ?? "preview",
          generationId: "preview",
          content: "请帮我分析一下这段对话，并给出下一步建议。",
          assistantContent: "",
          startedAt: previewStartedAt,
          status: "starting" as const,
        }
      : null);
  const displayedTurns = currentPendingRequest
    ? (view?.turns.filter((turn) => turn.status !== "pending") ?? [])
    : (view?.turns ?? []);
  const hasTurns = displayedTurns.length > 0;
  const hasActivity =
    hasTurns || displayedPendingRequest !== null || displayedError !== null;

  const clearPreview = () => {
    setPreviewMode(null);
    const url = new URL(window.location.href);
    url.searchParams.delete("preview");
    window.history.replaceState({}, "", url);
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.headerContent}>
          {!sidebarOpen ? (
            <IconButton label="打开侧边栏" onClick={onOpenSidebar}>
              <PanelLeftOpen size={17} />
            </IconButton>
          ) : null}

          <div className={styles.titleGroup}>
            <span className={styles.title}>{view?.title ?? "新对话"}</span>
          </div>
        </div>
      </header>

      <main className={styles.main}>
        {isLoading ? (
          <div className={styles.loading} aria-live="polite">
            <span />
            <span />
            <span />
          </div>
        ) : null}

        {!isLoading && hasActivity ? (
          <div className={styles.turnList}>
            {displayedTurns.map((turn) => (
              <MessageTurn
                key={`${view?.activeBranchId ?? "no-branch"}-${turn.turnId}`}
                turn={turn}
                isEditing={editingTurnId === turn.turnId}
                editingContent={editingContent}
                disabled={isSubmitting || isGenerating}
                onStartEdit={() => startEditing(turn.turnId)}
                onEditingContentChange={changeEditingContent}
                onSaveEdit={() => void saveEditing()}
                onCancelEdit={cancelEditing}
                onSelectVariant={(direction) =>
                  void selectVariant(turn.turnId, direction)
                }
              />
            ))}

            {displayedPendingRequest ? (
              <PendingResponse request={displayedPendingRequest} />
            ) : null}

            {displayedError ? (
              <ErrorNotice
                error={displayedError}
                requestContent={
                  error
                    ? failedRequestContent
                    : previewMode === "llm"
                      ? "请继续分析这段对话，并给出具体建议。"
                      : null
                }
                onRetry={
                  displayedError.retryable
                    ? () => {
                        if (simulatedError) {
                          clearPreview();
                        } else if (failedRequestContent) {
                          void sendMessage(failedRequestContent);
                        } else {
                          void refresh();
                        }
                      }
                    : undefined
                }
                onDismiss={() => {
                  dismissError();
                  if (simulatedError) {
                    clearPreview();
                  }
                }}
              />
            ) : null}
          </div>
        ) : null}

        {!isLoading && !hasActivity ? (
          <section className={styles.emptyConversation}>
            <h1>开始一段新对话</h1>
            <p>输入消息后，新的会话会显示在左侧历史记录中。</p>
          </section>
        ) : null}

      </main>

      <div className={styles.composerDock}>
        <div className={styles.composerContent}>
          <Composer
            disabled={
              isLoading ||
              isSubmitting ||
              (isGenerating && currentPendingRequest === null)
            }
            generating={currentPendingRequest !== null}
            stopping={currentPendingRequest?.status === "stopping"}
            onSend={sendMessage}
            onStop={stopGeneration}
          />
          <p className={styles.disclaimer}>
            AI 可能会犯错，请核查重要信息。
          </p>
        </div>
      </div>
    </div>
  );
}

function readPreviewMode(): string | null {
  if (!import.meta.env.DEV) {
    return null;
  }

  const preview = new URLSearchParams(window.location.search).get("preview");
  return ["waiting", "llm", "network"].includes(preview ?? "")
    ? preview
    : null;
}
