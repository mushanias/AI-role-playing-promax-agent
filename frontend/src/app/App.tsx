import { useMemo, useState } from "react";

import { AppShell } from "./layout/AppShell";
import { ChatPage } from "../features/chat/components/ChatPage";
import { useConversationController } from "../features/chat/hooks/useConversationController";
import { HttpConversationGateway } from "../features/chat/services/HttpConversationGateway";
import { useLLMController } from "../features/llm/hooks/useLLMController";
import { HttpLLMGateway } from "../features/llm/services/HttpLLMGateway";
import { Sidebar } from "../features/navigation/components/Sidebar";
import type {
  ConversationListItem,
  DeletedConversationListItem,
} from "../features/navigation/model/types";
import { useBackendConnection } from "../shared/api/useBackendConnection";

const PINNED_CONVERSATIONS_KEY = "versioned-chat.pinned-conversations";

export default function App() {
  const conversationGateway = useMemo(
    () => new HttpConversationGateway(),
    [],
  );
  const llmGateway = useMemo(() => new HttpLLMGateway(), []);
  const backendStatus = useBackendConnection();
  const controller = useConversationController(conversationGateway);
  const llmController = useLLMController(
    llmGateway,
    backendStatus === "connected",
  );
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [pinnedConversationIds, setPinnedConversationIds] = useState<string[]>(
    readPinnedConversationIds,
  );
  const conversations = useMemo<ConversationListItem[]>(
    () =>
      controller.conversationList.map((conversation) => ({
        conversationId: conversation.conversationId,
        title: conversation.title,
        updatedLabel: formatUpdatedLabel(conversation.updatedAt),
        pinned: pinnedConversationIds.includes(conversation.conversationId),
      })),
    [controller.conversationList, pinnedConversationIds],
  );
  const deletedConversations = useMemo<DeletedConversationListItem[]>(
    () =>
      controller.deletedConversationList.map((conversation) => ({
        conversationId: conversation.conversationId,
        title: conversation.title,
        deletedLabel: formatDeletedLabel(conversation.deletedAt),
      })),
    [controller.deletedConversationList],
  );

  return (
    <AppShell
      sidebarOpen={sidebarOpen}
      onCloseSidebar={() => setSidebarOpen(false)}
      sidebar={
        <Sidebar
          conversations={conversations}
          deletedConversations={deletedConversations}
          activeConversationId={controller.view?.conversationId ?? null}
          modelOptions={llmController.modelOptions}
          selectedModelOptionId={llmController.selectedModelOptionId}
          apiConnected={llmController.isConnected}
          backendStatus={backendStatus}
          modelLoading={llmController.isLoading}
          modelBusy={llmController.isUpdating}
          modelStatusMessage={llmController.statusMessage}
          disabled={controller.isSubmitting || controller.isLoading}
          onClose={() => setSidebarOpen(false)}
          onNewConversation={() => {
            void controller.startNewConversation();
            closeSidebarOnNarrowScreen(setSidebarOpen);
          }}
          onSelectConversation={(conversationId) => {
            void controller.openConversation(conversationId);
            closeSidebarOnNarrowScreen(setSidebarOpen);
          }}
          onTogglePinned={(conversationId) => {
            setPinnedConversationIds((current) => {
              const next = current.includes(conversationId)
                ? current.filter((id) => id !== conversationId)
                : [...current, conversationId];
              window.localStorage.setItem(
                PINNED_CONVERSATIONS_KEY,
                JSON.stringify(next),
              );
              return next;
            });
          }}
          onDeleteConversation={controller.deleteConversation}
          onRestoreConversation={controller.restoreConversation}
          onSelectModel={llmController.selectModel}
          onConnectApiKey={llmController.connectApiKey}
        />
      }
    >
      <ChatPage
        controller={controller}
        sidebarOpen={sidebarOpen}
        onOpenSidebar={() => setSidebarOpen(true)}
      />
    </AppShell>
  );
}

function readPinnedConversationIds(): string[] {
  try {
    const value = JSON.parse(
      window.localStorage.getItem(PINNED_CONVERSATIONS_KEY) ?? "[]",
    );
    return Array.isArray(value)
      ? value.filter((item): item is string => typeof item === "string")
      : [];
  } catch {
    return [];
  }
}

function formatUpdatedLabel(updatedAt: string): string {
  const updatedTime = new Date(updatedAt).getTime();
  const elapsedSeconds = Math.max(0, (Date.now() - updatedTime) / 1000);

  if (elapsedSeconds < 60) {
    return "刚刚";
  }
  if (elapsedSeconds < 3600) {
    return `${Math.floor(elapsedSeconds / 60)} 分钟前`;
  }
  if (elapsedSeconds < 86400) {
    return `${Math.floor(elapsedSeconds / 3600)} 小时前`;
  }
  if (elapsedSeconds < 604800) {
    return `${Math.floor(elapsedSeconds / 86400)} 天前`;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
  }).format(new Date(updatedAt));
}

function formatDeletedLabel(deletedAt: string): string {
  const relativeTime = formatUpdatedLabel(deletedAt);
  return relativeTime === "刚刚" ? "刚刚删除" : `${relativeTime}删除`;
}

function closeSidebarOnNarrowScreen(
  setSidebarOpen: (open: boolean) => void,
): void {
  if (window.matchMedia("(max-width: 820px)").matches) {
    setSidebarOpen(false);
  }
}
