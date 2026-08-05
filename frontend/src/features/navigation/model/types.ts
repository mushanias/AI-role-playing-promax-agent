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
