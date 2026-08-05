import { API_BASE_URL } from "../../../config/runtime";
import {
  apiRequest,
  ApiRequestError,
  AUTH_REQUIRED_EVENT,
} from "../../../shared/api/ApiClient";
import type {
  ChatStreamEvent,
  ConversationTurn,
  ConversationSummary,
  ConversationView,
  RewriteUserMessageInput,
  SelectVariantInput,
  SendMessageInput,
} from "../model/types";
import type { ConversationGateway } from "./ConversationGateway";

interface ConversationCreateDto {
  conversation_id: string;
  active_branch_id: string;
}

interface ConversationListDto {
  conversations: Array<{
    conversation_id: string;
    title: string;
    updated_at: string;
  }>;
}

interface DeletedConversationListDto {
  conversations: Array<{
    conversation_id: string;
    title: string;
    deleted_at: string;
  }>;
}

interface HistoryTurnDto {
  turn_id: string;
  parent_turn_id: string | null;
  user_content: string;
  assistant_content: string | null;
  status: "pending" | "completed" | "failed";
  response_duration_ms: number | null;
  failure_message: string | null;
  finish_reason: "completed" | "stopped" | null;
  variant_index: number;
  variant_count: number;
}

interface ConversationHistoryDto {
  conversation_id: string;
  branch_id: string;
  active_branch_id: string;
  turns: HistoryTurnDto[];
}

interface TurnVariantDto {
  turn_id: string;
  branch_id: string;
  is_active: boolean;
}

interface TurnVariantsDto {
  variants: TurnVariantDto[];
}

const SESSION_CONVERSATION_KEY = "versioned-chat.current-conversation";

export class HttpConversationGateway implements ConversationGateway {
  private conversationId = window.sessionStorage.getItem(
    SESSION_CONVERSATION_KEY,
  );

  async getConversation(): Promise<ConversationView | null> {
    if (!this.conversationId) {
      return null;
    }

    try {
      return await this.getHistory(this.conversationId);
    } catch (error: unknown) {
      if (error instanceof ApiRequestError && error.status === 404) {
        this.clearCurrentConversation();
        return null;
      }
      throw error;
    }
  }

  async listConversations(): Promise<ConversationSummary[]> {
    const result = await apiRequest<ConversationListDto>("/conversations");
    return result.conversations.map((conversation) => ({
      conversationId: conversation.conversation_id,
      title: conversation.title,
      updatedAt: conversation.updated_at,
    }));
  }

  async listDeletedConversations() {
    const result = await apiRequest<DeletedConversationListDto>(
      "/conversations/trash",
    );
    return result.conversations.map((conversation) => ({
      conversationId: conversation.conversation_id,
      title: conversation.title,
      deletedAt: conversation.deleted_at,
    }));
  }

  async openConversation(
    conversationId: string,
  ): Promise<ConversationView> {
    const view = await this.getHistory(conversationId);
    this.conversationId = conversationId;
    window.sessionStorage.setItem(
      SESSION_CONVERSATION_KEY,
      conversationId,
    );
    return view;
  }

  async createConversation(): Promise<ConversationView> {
    const created = await apiRequest<ConversationCreateDto>("/conversations", {
      method: "POST",
    });
    this.conversationId = created.conversation_id;
    window.sessionStorage.setItem(
      SESSION_CONVERSATION_KEY,
      created.conversation_id,
    );

    return {
      conversationId: created.conversation_id,
      title: "新对话",
      activeBranchId: created.active_branch_id,
      turns: [],
    };
  }

  clearCurrentConversation(): void {
    this.conversationId = null;
    window.sessionStorage.removeItem(SESSION_CONVERSATION_KEY);
  }

  async deleteConversation(conversationId: string): Promise<void> {
    await apiRequest<void>(
      `/conversations/${encodeURIComponent(conversationId)}`,
      { method: "DELETE" },
    );

    if (this.conversationId === conversationId) {
      this.clearCurrentConversation();
    }
  }

  async restoreConversation(conversationId: string): Promise<void> {
    await apiRequest<void>(
      `/conversations/trash/${encodeURIComponent(conversationId)}/restore`,
      { method: "POST" },
    );
  }

  async rewriteUserMessage(
    input: RewriteUserMessageInput,
  ): Promise<ConversationView> {
    await apiRequest(
      `/conversations/${encodeURIComponent(input.conversationId)}` +
        `/turns/${encodeURIComponent(input.turnId)}/rewrite`,
      {
        method: "POST",
        body: JSON.stringify({
          message: input.content,
          source_branch_id: input.sourceBranchId,
        }),
      },
    );
    return this.getHistory(input.conversationId);
  }

  async selectVariant(input: SelectVariantInput): Promise<ConversationView> {
    const variants = await apiRequest<TurnVariantsDto>(
      `/conversations/${encodeURIComponent(input.conversationId)}` +
        `/turns/${encodeURIComponent(input.turnId)}/variants`,
    );
    const currentIndex = variants.variants.findIndex(
      (variant) => variant.is_active,
    );
    const targetIndex = Math.min(
      variants.variants.length - 1,
      Math.max(0, currentIndex + input.direction),
    );
    const target = variants.variants[targetIndex];

    if (!target || targetIndex === currentIndex) {
      return this.getHistory(input.conversationId);
    }

    await apiRequest(
      `/conversations/${encodeURIComponent(input.conversationId)}` +
        `/branches/${encodeURIComponent(target.branch_id)}/activate`,
      { method: "POST" },
    );
    return this.getHistory(input.conversationId);
  }

  async sendMessage(input: SendMessageInput): Promise<ConversationView> {
    await apiRequest(
      `/conversations/${encodeURIComponent(input.conversationId)}/turns`,
      {
        method: "POST",
        body: JSON.stringify({
          message: input.content,
          branch_id: input.branchId,
        }),
      },
    );
    return this.getHistory(input.conversationId);
  }

  async streamMessage(
    input: SendMessageInput & { generationId: string },
    onEvent: (event: ChatStreamEvent) => void,
  ): Promise<ConversationView> {
    await streamChatRequest(
      `/conversations/${encodeURIComponent(input.conversationId)}` +
        "/turns/stream",
      {
        generation_id: input.generationId,
        message: input.content,
        branch_id: input.branchId,
      },
      onEvent,
    );
    return this.getHistory(input.conversationId);
  }

  async streamRewriteUserMessage(
    input: RewriteUserMessageInput & { generationId: string },
    onEvent: (event: ChatStreamEvent) => void,
  ): Promise<ConversationView> {
    await streamChatRequest(
      `/conversations/${encodeURIComponent(input.conversationId)}` +
        `/turns/${encodeURIComponent(input.turnId)}/rewrite/stream`,
      {
        generation_id: input.generationId,
        message: input.content,
        source_branch_id: input.sourceBranchId,
      },
      onEvent,
    );
    return this.getHistory(input.conversationId);
  }

  async stopGeneration(generationId: string): Promise<void> {
    await apiRequest<void>(
      `/generations/${encodeURIComponent(generationId)}/stop`,
      { method: "POST" },
    );
  }

  private async getHistory(
    conversationId: string,
  ): Promise<ConversationView> {
    const history = await apiRequest<ConversationHistoryDto>(
      `/conversations/${encodeURIComponent(conversationId)}/history`,
    );
    const turns = history.turns.map(mapTurn);

    return {
      conversationId: history.conversation_id,
      title: buildConversationTitle(turns),
      activeBranchId: history.active_branch_id,
      turns,
    };
  }
}

function mapTurn(turn: HistoryTurnDto): ConversationTurn {
  return {
    turnId: turn.turn_id,
    parentTurnId: turn.parent_turn_id,
    branchId: "",
    userContent: turn.user_content,
    assistantContent: turn.assistant_content,
    status: turn.status,
    responseDurationMs: turn.response_duration_ms,
    failureMessage: turn.failure_message,
    finishReason: turn.finish_reason,
    variantIndex: turn.variant_index + 1,
    variantCount: turn.variant_count,
  };
}

interface StreamErrorPayload {
  error?: { code?: string; message?: string };
  detail?: string | Array<{ msg?: string }>;
}

async function streamChatRequest(
  path: string,
  body: Record<string, unknown>,
  onEvent: (event: ChatStreamEvent) => void,
): Promise<void> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      credentials: "include",
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiRequestError(
      "无法连接后端，请确认 FastAPI 已在 8000 端口启动",
      0,
      "network_error",
    );
  }

  if (!response.ok) {
    if (response.status === 401) {
      window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT));
    }
    const payload = (await response.json().catch(() => null)) as
      | StreamErrorPayload
      | null;
    const validationMessage = Array.isArray(payload?.detail)
      ? payload.detail[0]?.msg
      : payload?.detail;
    throw new ApiRequestError(
      payload?.error?.message ||
        validationMessage ||
        `后端请求失败（${response.status}）`,
      response.status,
      payload?.error?.code,
    );
  }

  if (!response.body) {
    throw new ApiRequestError(
      "浏览器没有收到流式响应内容",
      502,
      "llm_response_error",
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let terminalReceived = false;

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    buffer = buffer.replace(/\r\n/g, "\n");

    let separatorIndex = buffer.indexOf("\n\n");
    while (separatorIndex >= 0) {
      const rawEvent = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);
      const event = parseSseEvent(rawEvent);
      if (event) {
        onEvent(event);
        if (event.type === "failed") {
          throw new ApiRequestError(
            event.message ?? "流式回答生成失败",
            event.status ?? 500,
            event.code,
          );
        }
        if (event.type === "completed" || event.type === "stopped") {
          terminalReceived = true;
        }
      }
      separatorIndex = buffer.indexOf("\n\n");
    }

    if (done) {
      break;
    }
  }

  if (!terminalReceived) {
    throw new ApiRequestError(
      "流式连接提前结束，请重试当前消息",
      502,
      "llm_response_error",
    );
  }
}

function parseSseEvent(rawEvent: string): ChatStreamEvent | null {
  let eventType = "message";
  const dataLines: string[] = [];

  for (const line of rawEvent.split("\n")) {
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  const payload = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
  return {
    type: eventType as ChatStreamEvent["type"],
    generationId: String(payload.generation_id ?? ""),
    conversationId: optionalString(payload.conversation_id),
    branchId: optionalString(payload.branch_id),
    turnId: optionalString(payload.turn_id),
    content: optionalString(payload.content),
    durationMs: optionalNumber(payload.duration_ms),
    finishReason: optionalString(payload.finish_reason) as
      | ChatStreamEvent["finishReason"]
      | undefined,
    code: optionalString(payload.code),
    message: optionalString(payload.message),
    status: optionalNumber(payload.status),
  };
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function optionalNumber(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined;
}

function buildConversationTitle(turns: ConversationTurn[]): string {
  const firstMessage = turns[0]?.userContent.trim();

  if (!firstMessage) {
    return "新对话";
  }

  return firstMessage.length > 22
    ? `${firstMessage.slice(0, 22)}…`
    : firstMessage;
}
