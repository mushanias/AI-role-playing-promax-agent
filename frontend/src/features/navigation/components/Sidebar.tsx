import { useState } from "react";
import {
  Bot,
  Check,
  ChevronLeft,
  ChevronRight,
  GitBranch,
  KeyRound,
  LogOut,
  MessageSquarePlus,
  PanelLeftClose,
  Pin,
  RotateCcw,
  Trash2,
  UserRound,
} from "lucide-react";

import { IconButton } from "../../../shared/ui/IconButton";
import type { BackendConnectionStatus } from "../../../shared/api/useBackendConnection";
import type { LLMProviderState } from "../../llm/model/types";
import type {
  ConversationListItem,
  DeletedConversationListItem,
} from "../model/types";
import styles from "./Sidebar.module.css";

export interface SidebarProps {
  conversations: ConversationListItem[];
  deletedConversations: DeletedConversationListItem[];
  activeConversationId: string | null;
  providers: LLMProviderState[];
  activeProviderId: string;
  activeModelId: string;
  backendStatus: BackendConnectionStatus;
  modelLoading?: boolean;
  modelBusy?: boolean;
  modelStatusMessage?: string | null;
  disabled?: boolean;
  accountName: string;
  onClose(): void;
  onNewConversation(): void;
  onSelectConversation(conversationId: string): void;
  onTogglePinned(conversationId: string): void;
  onDeleteConversation(conversationId: string): Promise<boolean>;
  onRestoreConversation(conversationId: string): Promise<boolean>;
  onSelectModel(providerId: string, modelId: string): Promise<boolean>;
  onConnectProvider(
    providerId: string,
    modelId: string,
    apiKey: string,
  ): Promise<boolean>;
  onVerifyLocalConfig(): Promise<boolean>;
  onLogout(): Promise<void>;
}

export function Sidebar({
  conversations,
  deletedConversations,
  activeConversationId,
  providers,
  activeProviderId,
  activeModelId,
  backendStatus,
  modelLoading = false,
  modelBusy = false,
  modelStatusMessage = null,
  disabled = false,
  accountName,
  onClose,
  onNewConversation,
  onSelectConversation,
  onTogglePinned,
  onDeleteConversation,
  onRestoreConversation,
  onSelectModel,
  onConnectProvider,
  onVerifyLocalConfig,
  onLogout,
}: SidebarProps) {
  const [modelMenuOpen, setModelMenuOpen] = useState(false);
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(
    null,
  );
  const [keyEditorOpen, setKeyEditorOpen] = useState(false);
  const [trashOpen, setTrashOpen] = useState(false);
  const [apiKeyDraft, setApiKeyDraft] = useState("");

  const activeProvider = providers.find(
    (provider) => provider.providerId === activeProviderId,
  );
  const selectedProvider = providers.find(
    (provider) => provider.providerId === selectedProviderId,
  );
  const pinnedConversations = conversations.filter((item) => item.pinned);
  const recentConversations = conversations.filter((item) => !item.pinned);
  const backendConnected = backendStatus === "connected";
  const modelUnavailable =
    !backendConnected || modelLoading || modelBusy || providers.length === 0;
  const modelMeta =
    backendStatus === "checking"
      ? "检测中"
      : !backendConnected
        ? "不可用"
        : modelLoading
          ? "加载中"
          : activeProvider
            ? formatActiveModelLabel(activeProvider.name, activeModelId)
            : "暂无模型";

  return (
    <div className={styles.sidebarContent}>
      <div className={styles.brandRow}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>
            <GitBranch size={16} strokeWidth={2} />
          </span>
          <span>分支对话</span>
        </div>

        <IconButton label="收起侧边栏" onClick={onClose}>
          <PanelLeftClose size={17} />
        </IconButton>
      </div>

      <nav className={styles.primaryActions} aria-label="主要操作">
        <button
          type="button"
          className={styles.actionButton}
          disabled={disabled}
          onClick={() => {
            onNewConversation();
            setModelMenuOpen(false);
            setSelectedProviderId(null);
            setKeyEditorOpen(false);
            setTrashOpen(false);
          }}
        >
          <MessageSquarePlus size={17} />
          <span>新对话</span>
        </button>

        <button
          type="button"
          className={styles.actionButton}
          disabled={modelUnavailable}
          aria-expanded={modelMenuOpen}
          onClick={() => {
            setModelMenuOpen((open) => {
              const nextOpen = !open;
              if (nextOpen) {
                setSelectedProviderId(null);
                setKeyEditorOpen(false);
              }
              return nextOpen;
            });
            setTrashOpen(false);
          }}
        >
          <Bot size={17} />
          <span>切换模型</span>
          <span className={styles.actionMeta}>{modelMeta}</span>
        </button>

        {modelMenuOpen ? (
          <div className={styles.inlinePanel}>
            {selectedProvider ? (
              <>
                <button
                  type="button"
                  className={styles.panelBack}
                  onClick={() => {
                    setSelectedProviderId(null);
                    setKeyEditorOpen(false);
                    setApiKeyDraft("");
                  }}
                >
                  <ChevronLeft size={14} />
                  <span>{selectedProvider.name}</span>
                </button>

                <div className={styles.providerSummary}>
                  <span
                    className={styles.connectionStatus}
                    data-connected={selectedProvider.configured}
                  >
                    {getProviderStatus(selectedProvider)}
                  </span>
                  <small>同一厂商的模型共用一个 API Key</small>
                </div>

                <div className={styles.modelListLabel}>选择模型</div>
                {selectedProvider.models.map((modelId) => {
                  const active =
                    selectedProvider.active && modelId === activeModelId;
                  return (
                    <button
                      key={modelId}
                      type="button"
                      className={styles.modelOption}
                      disabled={modelBusy || !selectedProvider.configured}
                      data-selected={active}
                      onClick={async () => {
                        const success = await onSelectModel(
                          selectedProvider.providerId,
                          modelId,
                        );
                        if (success) {
                          setModelMenuOpen(false);
                        }
                      }}
                    >
                      <span>
                        <strong>{modelId}</strong>
                        {!selectedProvider.configured ? (
                          <small>连接 API Key 后可用</small>
                        ) : null}
                      </span>
                      {active ? (
                        <Check size={15} />
                      ) : !selectedProvider.configured ? (
                        <KeyRound size={13} />
                      ) : null}
                    </button>
                  );
                })}

                <button
                  type="button"
                  className={styles.keyAction}
                  disabled={modelBusy}
                  aria-expanded={keyEditorOpen}
                  onClick={() => setKeyEditorOpen((open) => !open)}
                >
                  <KeyRound size={14} />
                  <span>
                    {selectedProvider.configured
                      ? "更换 API Key"
                      : `连接 ${shortProviderName(selectedProvider.name)} API Key`}
                  </span>
                </button>

                {keyEditorOpen ? (
                  <form
                    className={styles.apiForm}
                    onSubmit={async (event) => {
                      event.preventDefault();
                      const apiKey = apiKeyDraft.trim();
                      if (!apiKey) {
                        return;
                      }

                      const targetModel =
                        selectedProvider.active &&
                        selectedProvider.models.includes(activeModelId)
                          ? activeModelId
                          : selectedProvider.defaultModel;
                      const success = await onConnectProvider(
                        selectedProvider.providerId,
                        targetModel,
                        apiKey,
                      );
                      if (success) {
                        setApiKeyDraft("");
                        setKeyEditorOpen(false);
                      }
                    }}
                  >
                    <label className={styles.apiField}>
                      <span>{selectedProvider.name} API Key</span>
                      <input
                        type="password"
                        value={apiKeyDraft}
                        autoComplete="off"
                        placeholder="输入 API Key"
                        onChange={(event) =>
                          setApiKeyDraft(event.target.value)
                        }
                      />
                    </label>
                    <div className={styles.apiFooter}>
                      <small>仅发送到本地后端，不写入浏览器存储</small>
                      <button
                        type="submit"
                        disabled={modelBusy || !apiKeyDraft.trim()}
                      >
                        {modelBusy ? "验证中" : "连接"}
                      </button>
                    </div>
                  </form>
                ) : null}

                {selectedProvider.active && selectedProvider.configured ? (
                  <button
                    type="button"
                    className={styles.verifyLocalButton}
                    disabled={modelBusy}
                    onClick={() => void onVerifyLocalConfig()}
                  >
                    {modelBusy ? "验证中" : "测试当前配置"}
                  </button>
                ) : null}
                {modelStatusMessage ? (
                  <p className={styles.modelStatus}>{modelStatusMessage}</p>
                ) : null}
              </>
            ) : (
              providers.map((provider) => (
                <button
                  key={provider.providerId}
                  type="button"
                  className={styles.providerOption}
                  disabled={modelBusy}
                  data-selected={provider.active}
                  onClick={() => {
                    setSelectedProviderId(provider.providerId);
                    setKeyEditorOpen(false);
                    setApiKeyDraft("");
                  }}
                >
                  <span>
                    <strong>{provider.name}</strong>
                    <small>{getProviderStatus(provider)}</small>
                  </span>
                  <ChevronRight size={14} />
                </button>
              ))
            )}
          </div>
        ) : null}
      </nav>

      <div className={styles.history}>
        {pinnedConversations.length > 0 ? (
          <HistorySection
            title="置顶"
            items={pinnedConversations}
            activeConversationId={activeConversationId}
            onSelectConversation={onSelectConversation}
            onTogglePinned={onTogglePinned}
            onDeleteConversation={onDeleteConversation}
          />
        ) : null}

        <HistorySection
          title="历史对话"
          items={recentConversations}
          activeConversationId={activeConversationId}
          onSelectConversation={onSelectConversation}
          onTogglePinned={onTogglePinned}
          onDeleteConversation={onDeleteConversation}
        />
      </div>

      <div className={styles.sidebarBottom}>
        {trashOpen ? (
          <section className={styles.trashPanel} aria-label="回收站内容">
            {deletedConversations.length > 0 ? (
              <div className={styles.trashList}>
                {deletedConversations.map((item) => (
                  <div
                    key={item.conversationId}
                    className={styles.trashItem}
                  >
                    <span className={styles.trashItemContent}>
                      <span className={styles.trashTitle}>{item.title}</span>
                      <span className={styles.trashTime}>
                        {item.deletedLabel}
                      </span>
                    </span>
                    <IconButton
                      label={`恢复${item.title}`}
                      className={styles.restoreButton}
                      disabled={disabled}
                      onClick={() => {
                        void onRestoreConversation(item.conversationId);
                      }}
                    >
                      <RotateCcw size={14} />
                    </IconButton>
                  </div>
                ))}
              </div>
            ) : (
              <p className={styles.emptyTrash}>回收站是空的</p>
            )}
          </section>
        ) : null}

        <button
          type="button"
          className={styles.trashToggle}
          aria-expanded={trashOpen}
          disabled={disabled}
          onClick={() => {
            setTrashOpen((open) => !open);
            setModelMenuOpen(false);
            setSelectedProviderId(null);
            setKeyEditorOpen(false);
          }}
        >
          <Trash2 size={16} />
          <span>回收站</span>
          {deletedConversations.length > 0 ? (
            <span className={styles.trashCount}>
              {deletedConversations.length}
            </span>
          ) : null}
        </button>

        <div className={styles.accountRow}>
          <span className={styles.accountIdentity}>
            <UserRound size={15} />
            <span>{accountName}</span>
          </span>
          <button
            type="button"
            className={styles.logoutButton}
            aria-label="退出登录"
            title="退出登录"
            onClick={() => void onLogout()}
          >
            <LogOut size={15} />
            <span>退出</span>
          </button>
        </div>

        <div className={styles.sidebarFooter} role="status" aria-live="polite">
          <span className={styles.localDot} data-status={backendStatus} />
          {backendStatus === "checking"
            ? "正在检测本地后端"
            : backendConnected
              ? "本地后端已连接"
              : "本地后端未连接"}
        </div>
      </div>
    </div>
  );
}

function getProviderStatus(provider: LLMProviderState): string {
  if (provider.active && provider.verified) {
    return "正在使用 · 已验证";
  }
  if (provider.active && provider.configured) {
    return "正在使用 · 已配置";
  }
  return provider.configured ? "本次已连接" : "未配置";
}

function formatActiveModelLabel(
  providerName: string,
  modelId: string,
): string {
  const provider = shortProviderName(providerName);
  const prefix = `${provider}-`;
  const model = modelId.toLowerCase().startsWith(prefix.toLowerCase())
    ? modelId.slice(prefix.length)
    : modelId;
  return `${provider} · ${model}`;
}

function shortProviderName(providerName: string): string {
  return providerName.split("/")[0].trim();
}

interface HistorySectionProps {
  title: string;
  items: ConversationListItem[];
  activeConversationId: string | null;
  onSelectConversation(conversationId: string): void;
  onTogglePinned(conversationId: string): void;
  onDeleteConversation(conversationId: string): Promise<boolean>;
}

function HistorySection({
  title,
  items,
  activeConversationId,
  onSelectConversation,
  onTogglePinned,
  onDeleteConversation,
}: HistorySectionProps) {
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  return (
    <section className={styles.historySection}>
      <h2>{title}</h2>

      {items.length > 0 ? (
        <div className={styles.historyList}>
          {items.map((item) => (
            <div
              key={item.conversationId}
              className={styles.historyItem}
              data-active={item.conversationId === activeConversationId}
            >
              <button
                type="button"
                className={styles.historyMain}
                onClick={() => onSelectConversation(item.conversationId)}
              >
                <span className={styles.historyTitle}>{item.title}</span>
                <span className={styles.historyTime}>{item.updatedLabel}</span>
              </button>

              <IconButton
                label={item.pinned ? "取消置顶" : "置顶对话"}
                className={styles.pinButton}
                onClick={() => onTogglePinned(item.conversationId)}
              >
                <Pin
                  size={14}
                  fill={item.pinned ? "currentColor" : "none"}
                />
              </IconButton>

              <IconButton
                label="删除对话"
                className={styles.deleteButton}
                onClick={() => setPendingDeleteId(item.conversationId)}
              >
                <Trash2 size={14} />
              </IconButton>

              {pendingDeleteId === item.conversationId ? (
                <div
                  className={styles.deleteConfirm}
                  role="group"
                  aria-label={`确认删除${item.title}`}
                >
                  <span>移到回收站？</span>
                  <button
                    type="button"
                    className={styles.deleteCancel}
                    onClick={() => setPendingDeleteId(null)}
                  >
                    取消
                  </button>
                  <button
                    type="button"
                    className={styles.deleteSubmit}
                    onClick={async () => {
                      await onDeleteConversation(item.conversationId);
                      setPendingDeleteId(null);
                    }}
                  >
                    移入
                  </button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <p className={styles.emptyHistory}>
          还没有历史对话，快来开启一段新的冒险吧～
        </p>
      )}
    </section>
  );
}
