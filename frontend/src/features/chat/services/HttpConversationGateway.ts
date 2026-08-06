import { apiRequest, ApiRequestError } from "../../../shared/api/ApiClient";
import type {
  ConversationTurn,
  ConversationSummary,
  ConversationView,
  GenerationSnapshot,
  GenerationStatus,
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

interface GenerationStatusDto {
  generation_id: string;
  status: GenerationStatus;
  conversation_id: string;
  branch_id: string | null;
  turn_id: string | null;
  content: string;
  duration_ms: number | null;
  finish_reason: "completed" | "stopped" | null;
  error_code: string | null;
  error_message: string | null;
  error_status: number | null;
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

  async startMessageGeneration(
    input: SendMessageInput & { generationId: string },
  ): Promise<void> {
    await apiRequest(
      `/conversations/${encodeURIComponent(input.conversationId)}` +
        "/turns/generations",
      {
        method: "POST",
        body: JSON.stringify({
          generation_id: input.generationId,
          message: input.content,
          branch_id: input.branchId,
        }),
      },
    );
  }

  async startRewriteGeneration(
    input: RewriteUserMessageInput & { generationId: string },
  ): Promise<void> {
    await apiRequest(
      `/conversations/${encodeURIComponent(input.conversationId)}` +
        `/turns/${encodeURIComponent(input.turnId)}/rewrite/generations`,
      {
        method: "POST",
        body: JSON.stringify({
          generation_id: input.generationId,
          message: input.content,
          source_branch_id: input.sourceBranchId,
        }),
      },
    );
  }

  async getGeneration(generationId: string): Promise<GenerationSnapshot> {
    const result = await apiRequest<GenerationStatusDto>(
      `/generations/${encodeURIComponent(generationId)}`,
      { timeoutMs: 5_000 },
    );
    return {
      generationId: result.generation_id,
      status: result.status,
      conversationId: result.conversation_id,
      branchId: result.branch_id,
      turnId: result.turn_id,
      content: result.content,
      durationMs: result.duration_ms,
      finishReason: result.finish_reason,
      code: result.error_code ?? undefined,
      message: result.error_message ?? undefined,
      errorStatus: result.error_status ?? undefined,
    };
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

function buildConversationTitle(turns: ConversationTurn[]): string {
  const firstMessage = turns[0]?.userContent.trim();

  if (!firstMessage) {
    return "新对话";
  }

  return firstMessage.length > 22
    ? `${firstMessage.slice(0, 22)}…`
    : firstMessage;
}
