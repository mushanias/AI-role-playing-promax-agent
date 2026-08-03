export interface ConversationListItem {
  conversationId: string;
  title: string;
  updatedLabel: string;
  pinned: boolean;
}

export interface DeletedConversationListItem {
  conversationId: string;
  title: string;
  deletedLabel: string;
}

export interface ModelOption {
  optionId: string;
  providerId: string;
  modelId: string;
  label: string;
  description: string;
}
