import { useCallback, useEffect, useState } from "react";

import type {
  ConversationSummary,
  ConversationView,
  DeletedConversationSummary,
  PendingRequest,
} from "../model/types";
import type { UserFacingError } from "../model/userFacingError";
import type { ConversationGateway } from "../services/ConversationGateway";
import { toUserFacingError } from "../services/errorPresentation";

export interface ConversationController {
  view: ConversationView | null;
  conversationList: ConversationSummary[];
  deletedConversationList: DeletedConversationSummary[];
  isLoading: boolean;
  isSubmitting: boolean;
  error: UserFacingError | null;
  pendingRequest: PendingRequest | null;
  failedRequestContent: string | null;
  editingTurnId: string | null;
  editingContent: string;
  startNewConversation(): Promise<void>;
  openConversation(conversationId: string): Promise<void>;
  deleteConversation(conversationId: string): Promise<boolean>;
  restoreConversation(conversationId: string): Promise<boolean>;
  startEditing(turnId: string): void;
  changeEditingContent(content: string): void;
  saveEditing(): Promise<void>;
  cancelEditing(): void;
  selectVariant(turnId: string, direction: -1 | 1): Promise<void>;
  sendMessage(content: string): Promise<void>;
  dismissError(): void;
}

export function useConversationController(
  gateway: ConversationGateway,
): ConversationController {
  const [view, setView] = useState<ConversationView | null>(null);
  const [conversationList, setConversationList] = useState<
    ConversationSummary[]
  >([]);
  const [deletedConversationList, setDeletedConversationList] = useState<
    DeletedConversationSummary[]
  >([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<UserFacingError | null>(null);
  const [pendingRequest, setPendingRequest] = useState<PendingRequest | null>(
    null,
  );
  const [failedRequestContent, setFailedRequestContent] = useState<
    string | null
  >(null);
  const [editingTurnId, setEditingTurnId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState("");

  useEffect(() => {
    let isActive = true;

    gateway
      .getConversation()
      .then(async (nextView) => {
        const [conversations, deletedConversations] = await Promise.all([
          gateway.listConversations(),
          gateway.listDeletedConversations(),
        ]);
        return { nextView, conversations, deletedConversations };
      })
      .then(({ nextView, conversations, deletedConversations }) => {
        if (isActive) {
          setView(nextView);
          setConversationList(conversations);
          setDeletedConversationList(deletedConversations);
          setError(null);
        }
      })
      .catch((reason: unknown) => {
        if (isActive) {
          setError(toUserFacingError(reason));
        }
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [gateway]);

  const startEditing = useCallback(
    (turnId: string) => {
      const turn = view?.turns.find((candidate) => candidate.turnId === turnId);

      if (!turn) {
        return;
      }

      setEditingTurnId(turnId);
      setEditingContent(turn.userContent);
      setError(null);
      setFailedRequestContent(null);
    },
    [view],
  );

  const startNewConversation = useCallback(async () => {
    if (isSubmitting) {
      return;
    }

    gateway.clearCurrentConversation();
    setView(null);
    setError(null);
    setPendingRequest(null);
    setFailedRequestContent(null);
    setEditingTurnId(null);
    setEditingContent("");
  }, [gateway, isSubmitting]);

  const openConversation = useCallback(
    async (conversationId: string) => {
      if (isSubmitting) {
        return;
      }

      setIsSubmitting(true);
      setError(null);
      setFailedRequestContent(null);

      try {
        const nextView = await gateway.openConversation(conversationId);
        setView(nextView);
        setEditingTurnId(null);
        setEditingContent("");
      } catch (reason: unknown) {
        setError(toUserFacingError(reason));
      } finally {
        setIsSubmitting(false);
      }
    },
    [gateway, isSubmitting],
  );

  const deleteConversation = useCallback(
    async (conversationId: string): Promise<boolean> => {
      if (isSubmitting) {
        return false;
      }

      setIsSubmitting(true);
      setError(null);
      setFailedRequestContent(null);

      try {
        await gateway.deleteConversation(conversationId);
        const [remaining, deletedConversations] = await Promise.all([
          gateway.listConversations(),
          gateway.listDeletedConversations(),
        ]);

        if (view?.conversationId === conversationId) {
          const nextView = remaining[0]
            ? await gateway.openConversation(remaining[0].conversationId)
            : null;

          setView(nextView);
          setConversationList(remaining);
          setDeletedConversationList(deletedConversations);
          setEditingTurnId(null);
          setEditingContent("");
        } else {
          setConversationList(remaining);
          setDeletedConversationList(deletedConversations);
        }

        return true;
      } catch (reason: unknown) {
        setError(toUserFacingError(reason));
        return false;
      } finally {
        setIsSubmitting(false);
      }
    },
    [gateway, isSubmitting, view],
  );

  const restoreConversation = useCallback(
    async (conversationId: string): Promise<boolean> => {
      if (isSubmitting) {
        return false;
      }

      setIsSubmitting(true);
      setError(null);

      try {
        await gateway.restoreConversation(conversationId);
        const [conversations, deletedConversations] = await Promise.all([
          gateway.listConversations(),
          gateway.listDeletedConversations(),
        ]);
        setConversationList(conversations);
        setDeletedConversationList(deletedConversations);
        return true;
      } catch (reason: unknown) {
        setError(toUserFacingError(reason));
        return false;
      } finally {
        setIsSubmitting(false);
      }
    },
    [gateway, isSubmitting],
  );

  const cancelEditing = useCallback(() => {
    setEditingTurnId(null);
    setEditingContent("");
  }, []);

  const saveEditing = useCallback(async () => {
    if (!view || !editingTurnId || !editingContent.trim()) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setFailedRequestContent(null);

    try {
      const nextView = await gateway.rewriteUserMessage({
        conversationId: view.conversationId,
        sourceBranchId: view.activeBranchId,
        turnId: editingTurnId,
        content: editingContent,
      });
      setView(nextView);
      setConversationList(await gateway.listConversations());
      setEditingTurnId(null);
      setEditingContent("");
    } catch (reason: unknown) {
      setError(toUserFacingError(reason));
    } finally {
      setIsSubmitting(false);
    }
  }, [editingContent, editingTurnId, gateway, view]);

  const selectVariant = useCallback(
    async (turnId: string, direction: -1 | 1) => {
      if (!view || isSubmitting) {
        return;
      }

      setIsSubmitting(true);
      setError(null);
      setFailedRequestContent(null);

      try {
        const nextView = await gateway.selectVariant({
          conversationId: view.conversationId,
          turnId,
          direction,
        });
        setView(nextView);
        setConversationList(await gateway.listConversations());
        setEditingTurnId(null);
        setEditingContent("");
      } catch (reason: unknown) {
        setError(toUserFacingError(reason));
      } finally {
        setIsSubmitting(false);
      }
    },
    [gateway, isSubmitting, view],
  );

  const sendMessage = useCallback(
    async (content: string) => {
      const normalizedContent = content.trim();

      if (!normalizedContent || isSubmitting) {
        return;
      }

      setIsSubmitting(true);
      setError(null);
      setFailedRequestContent(null);
      setPendingRequest({
        content: normalizedContent,
        startedAt: Date.now(),
      });

      try {
        const targetView = view ?? (await gateway.createConversation());
        if (!view) {
          setView(targetView);
        }
        const nextView = await gateway.sendMessage({
          conversationId: targetView.conversationId,
          branchId: targetView.activeBranchId,
          content: normalizedContent,
        });
        setView(nextView);
        setConversationList(await gateway.listConversations());
      } catch (reason: unknown) {
        setError(toUserFacingError(reason));
        setFailedRequestContent(normalizedContent);
      } finally {
        setPendingRequest(null);
        setIsSubmitting(false);
      }
    },
    [gateway, isSubmitting, view],
  );

  return {
    view,
    conversationList,
    deletedConversationList,
    isLoading,
    isSubmitting,
    error,
    pendingRequest,
    failedRequestContent,
    editingTurnId,
    editingContent,
    startNewConversation,
    openConversation,
    deleteConversation,
    restoreConversation,
    startEditing,
    changeEditingContent: setEditingContent,
    saveEditing,
    cancelEditing,
    selectVariant,
    sendMessage,
    dismissError: () => {
      setError(null);
      setFailedRequestContent(null);
    },
  };
}
