import { useState } from "react";
import {
  Bot,
  Check,
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
import type {
  ConversationListItem,
  DeletedConversationListItem,
  ModelOption,
} from "../model/types";
import styles from "./Sidebar.module.css";

export interface SidebarProps {
  conversations: ConversationListItem[];
  deletedConversations: DeletedConversationListItem[];
  activeConversationId: string | null;
  modelOptions: ModelOption[];
  selectedModelOptionId: string;
  apiConnected: boolean;
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
  onSelectModel(optionId: string): Promise<void>;
  onConnectApiKey(apiKey: string): Promise<boolean>;
  onLogout(): Promise<void>;
}

export function Sidebar({
  conversations,
  deletedConversations,
  activeConversationId,
  modelOptions,
  selectedModelOptionId,
  apiConnected,
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
  onConnectApiKey,
  onLogout,
}: SidebarProps) {
  const [modelMenuOpen, setModelMenuOpen] = useState(false);
  const [apiPanelOpen, setApiPanelOpen] = useState(false);
  const [trashOpen, setTrashOpen] = useState(false);
  const [apiKeyDraft, setApiKeyDraft] = useState("");

  const selectedModel =
    modelOptions.find(
      (model) => model.optionId === selectedModelOptionId,
    ) ?? modelOptions[0];
  const pinnedConversations = conversations.filter((item) => item.pinned);
  const recentConversations = conversations.filter((item) => !item.pinned);
  const backendConnected = backendStatus === "connected";
  const modelUnavailable =
    !backendConnected || modelLoading || modelBusy || !selectedModel;
  const modelMeta =
    backendStatus === "checking"
      ? "检测中"
      : !backendConnected
        ? "不可用"
        : modelLoading
          ? "加载中"
          : selectedModel?.label ?? "暂无模型";
  const apiStatus =
    backendStatus === "checking"
      ? "检测中"
      : !backendConnected
        ? "后端未连接"
        : modelLoading
          ? "加载中"
          : modelBusy
            ? "连接中"
            : apiConnected
              ? "已连接"
              : "未连接";

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
            setApiPanelOpen(false);
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
            setModelMenuOpen((open) => !open);
            setApiPanelOpen(false);
            setTrashOpen(false);
          }}
        >
          <Bot size={17} />
          <span>切换模型</span>
          <span className={styles.actionMeta}>{modelMeta}</span>
        </button>

        {modelMenuOpen ? (
          <div className={styles.inlinePanel}>
            {modelOptions.map((model) => (
              <button
                key={model.optionId}
                type="button"
                className={styles.modelOption}
                disabled={modelBusy}
                data-selected={model.optionId === selectedModelOptionId}
                onClick={() => {
                  void onSelectModel(model.optionId);
                  setModelMenuOpen(false);
                }}
              >
                <span>
                  <strong>{model.label}</strong>
                  <small>{model.description}</small>
                </span>
                {model.optionId === selectedModelOptionId ? (
                  <Check size={15} />
                ) : null}
              </button>
            ))}
          </div>
        ) : null}

        <button
          type="button"
          className={styles.actionButton}
          disabled={modelUnavailable}
          aria-expanded={apiPanelOpen}
          onClick={() => {
            setApiPanelOpen((open) => !open);
            setModelMenuOpen(false);
            setTrashOpen(false);
          }}
        >
          <KeyRound size={17} />
          <span>连接 API Key</span>
          <span
            className={styles.connectionStatus}
            data-connected={backendConnected && apiConnected}
          >
            {apiStatus}
          </span>
        </button>

        {apiPanelOpen ? (
          <form
            className={styles.inlinePanel}
            onSubmit={async (event) => {
              event.preventDefault();
              const apiKey = apiKeyDraft.trim();

              if (!apiKey) {
                return;
              }

              const success = await onConnectApiKey(apiKey);
              if (success) {
                setApiKeyDraft("");
                setApiPanelOpen(false);
              }
            }}
          >
            <label className={styles.apiField}>
              <span>API Key</span>
              <input
                type="password"
                value={apiKeyDraft}
                autoComplete="off"
                placeholder="sk-..."
                onChange={(event) => setApiKeyDraft(event.target.value)}
              />
            </label>
            <div className={styles.apiFooter}>
              <small>仅发送到本地后端，不写入浏览器存储</small>
              <button
                type="submit"
                disabled={modelBusy || !apiKeyDraft.trim()}
              >
                {modelBusy ? "连接中" : "连接"}
              </button>
            </div>
            {modelStatusMessage ? (
              <p className={styles.modelStatus}>{modelStatusMessage}</p>
            ) : null}
          </form>
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
            setApiPanelOpen(false);
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
