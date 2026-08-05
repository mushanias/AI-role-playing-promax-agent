export type TurnStatus = "pending" | "completed" | "failed";
export type TurnFinishReason = "completed" | "stopped";

export interface ConversationTurn {
  turnId: string;
  parentTurnId: string | null;
  branchId: string;
  userContent: string;
  assistantContent: string | null;
  status: TurnStatus;
  responseDurationMs?: number | null;
  failureMessage?: string | null;
  finishReason?: TurnFinishReason | null;
  variantIndex: number;
  variantCount: number;
}

export interface ConversationView {
  conversationId: string;
  title: string;
  activeBranchId: string;
  turns: ConversationTurn[];
}

export interface ConversationSummary {
  conversationId: string;
  title: string;
  updatedAt: string;
}

export interface DeletedConversationSummary {
  conversationId: string;
  title: string;
  deletedAt: string;
}

export interface RewriteUserMessageInput {
  conversationId: string;
  sourceBranchId: string;
  turnId: string;
  content: string;
}

export interface SelectVariantInput {
  conversationId: string;
  turnId: string;
  direction: -1 | 1;
}

export interface SendMessageInput {
  conversationId: string;
  branchId: string;
  content: string;
}

export interface PendingRequest {
  conversationId: string;
  generationId: string;
  content: string;
  assistantContent: string;
  startedAt: number;
  status: "starting" | "streaming" | "stopping";
}

export type ChatStreamEventType =
  | "started"
  | "delta"
  | "completed"
  | "stopped"
  | "failed";

export interface ChatStreamEvent {
  type: ChatStreamEventType;
  generationId: string;
  conversationId?: string;
  branchId?: string;
  turnId?: string;
  content?: string;
  durationMs?: number;
  finishReason?: TurnFinishReason;
  code?: string;
  message?: string;
  status?: number;
}
