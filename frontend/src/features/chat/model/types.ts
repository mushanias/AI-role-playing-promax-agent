export type TurnStatus = "pending" | "completed" | "failed";

export interface ConversationTurn {
  turnId: string;
  parentTurnId: string | null;
  branchId: string;
  userContent: string;
  assistantContent: string | null;
  status: TurnStatus;
  responseDurationMs?: number | null;
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
  content: string;
  startedAt: number;
}
