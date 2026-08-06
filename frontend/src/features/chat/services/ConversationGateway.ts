import type {
  DeletedConversationSummary,
  ConversationView,
  ConversationSummary,
  GenerationSnapshot,
  RewriteUserMessageInput,
  SelectVariantInput,
  SendMessageInput,
} from "../model/types";

export interface ConversationGateway {
  getConversation(): Promise<ConversationView | null>;
  listConversations(): Promise<ConversationSummary[]>;
  listDeletedConversations(): Promise<DeletedConversationSummary[]>;
  openConversation(conversationId: string): Promise<ConversationView>;

  createConversation(): Promise<ConversationView>;
  clearCurrentConversation(): void;
  deleteConversation(conversationId: string): Promise<void>;
  restoreConversation(conversationId: string): Promise<void>;

  rewriteUserMessage(
    input: RewriteUserMessageInput,
  ): Promise<ConversationView>;

  selectVariant(input: SelectVariantInput): Promise<ConversationView>;

  sendMessage(input: SendMessageInput): Promise<ConversationView>;

  startMessageGeneration(
    input: SendMessageInput & { generationId: string },
  ): Promise<void>;

  startRewriteGeneration(
    input: RewriteUserMessageInput & { generationId: string },
  ): Promise<void>;

  getGeneration(generationId: string): Promise<GenerationSnapshot>;

  stopGeneration(generationId: string): Promise<void>;
}
