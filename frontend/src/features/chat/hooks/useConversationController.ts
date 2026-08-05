import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";

import type {
  ConversationSummary,
  ConversationView,
  DeletedConversationSummary,
  ChatStreamEvent,
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
  isGenerating: boolean;
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
  stopGeneration(): Promise<void>;
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
  const activeConversationIdRef = useRef<string | null>(null);

  useEffect(() => {
    activeConversationIdRef.current = view?.conversationId ?? null;
  }, [view]);

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
      if (pendingRequest) {
        return;
      }
      const turn = view?.turns.find((candidate) => candidate.turnId === turnId);

      if (!turn) {
        return;
      }

      setEditingTurnId(turnId);
      setEditingContent(turn.userContent);
      setError(null);
      setFailedRequestContent(null);
    },
    [pendingRequest, view],
  );

  const startNewConversation = useCallback(async () => {
    if (isSubmitting) {
      return;
    }

    gateway.clearCurrentConversation();
    activeConversationIdRef.current = null;
    setView(null);
    setError(null);
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
        activeConversationIdRef.current = conversationId;
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
      if (
        isSubmitting ||
        pendingRequest?.conversationId === conversationId
      ) {
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
    [gateway, isSubmitting, pendingRequest, view],
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
    if (
      !view ||
      !editingTurnId ||
      !editingContent.trim() ||
      pendingRequest
    ) {
      return;
    }

    const sourceView = view;
    const targetIndex = view.turns.findIndex(
      (turn) => turn.turnId === editingTurnId,
    );
    if (targetIndex < 0) {
      return;
    }

    const generationId = crypto.randomUUID();
    const normalizedContent = editingContent.trim();
    setError(null);
    setFailedRequestContent(null);
    setEditingTurnId(null);
    setEditingContent("");
    setView({
      ...view,
      turns: view.turns.slice(0, targetIndex),
    });
    setPendingRequest({
      conversationId: view.conversationId,
      generationId,
      content: normalizedContent,
      assistantContent: "",
      startedAt: Date.now(),
      status: "starting",
    });

    try {
      const nextView = await gateway.streamRewriteUserMessage(
        {
          conversationId: view.conversationId,
          sourceBranchId: view.activeBranchId,
          turnId: editingTurnId,
          content: normalizedContent,
          generationId,
        },
        (event) => applyStreamEvent(event, generationId, setPendingRequest),
      );
      if (activeConversationIdRef.current === view.conversationId) {
        setView(nextView);
      }
      setConversationList(await gateway.listConversations());
    } catch (reason: unknown) {
      if (activeConversationIdRef.current === view.conversationId) {
        setView(sourceView);
        setError(toUserFacingError(reason));
      }
    } finally {
      setPendingRequest((current) =>
        current?.generationId === generationId ? null : current,
      );
    }
  }, [editingContent, editingTurnId, gateway, pendingRequest, view]);

  const selectVariant = useCallback(
    async (turnId: string, direction: -1 | 1) => {
      if (!view || isSubmitting || pendingRequest) {
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
    [gateway, isSubmitting, pendingRequest, view],
  );

  const sendMessage = useCallback(
    async (content: string) => {
      const normalizedContent = content.trim();

      if (!normalizedContent || isSubmitting || pendingRequest) {
        return;
      }

      setError(null);
      setFailedRequestContent(null);

      let targetConversationId: string | null = null;
      const generationId = crypto.randomUUID();
      try {
        const targetView = view ?? (await gateway.createConversation());
        targetConversationId = targetView.conversationId;
        if (!view) {
          activeConversationIdRef.current = targetView.conversationId;
          setView(targetView);
        }
        setPendingRequest({
          conversationId: targetView.conversationId,
          generationId,
          content: normalizedContent,
          assistantContent: "",
          startedAt: Date.now(),
          status: "starting",
        });
        const nextView = await gateway.streamMessage(
          {
            conversationId: targetView.conversationId,
            branchId: targetView.activeBranchId,
            content: normalizedContent,
            generationId,
          },
          (event) => applyStreamEvent(event, generationId, setPendingRequest),
        );
        if (
          activeConversationIdRef.current === targetView.conversationId
        ) {
          setView(nextView);
        }
        setConversationList(await gateway.listConversations());
      } catch (reason: unknown) {
        if (
          targetConversationId !== null &&
          activeConversationIdRef.current === targetConversationId
        ) {
          setError(toUserFacingError(reason));
          setFailedRequestContent(normalizedContent);
        }
      } finally {
        if (targetConversationId !== null) {
          setPendingRequest((current) =>
            current?.generationId === generationId ? null : current,
          );
        }
      }
    },
    [gateway, isSubmitting, pendingRequest, view],
  );

  const stopGeneration = useCallback(async () => {
    const currentGeneration = pendingRequest;
    if (!currentGeneration || currentGeneration.status === "stopping") {
      return;
    }

    setPendingRequest((current) =>
      current?.generationId === currentGeneration.generationId
        ? { ...current, status: "stopping" }
        : current,
    );
    try {
      await gateway.stopGeneration(currentGeneration.generationId);
    } catch (reason: unknown) {
      setError(toUserFacingError(reason));
      setPendingRequest((current) =>
        current?.generationId === currentGeneration.generationId
          ? { ...current, status: "streaming" }
          : current,
      );
    }
  }, [gateway, pendingRequest]);

  return {
    view,
    conversationList,
    deletedConversationList,
    isLoading,
    isSubmitting,
    isGenerating: pendingRequest !== null,
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
    stopGeneration,
    dismissError: () => {
      setError(null);
      setFailedRequestContent(null);
    },
  };
}

function applyStreamEvent(
  event: ChatStreamEvent,
  generationId: string,
  setPendingRequest: Dispatch<SetStateAction<PendingRequest | null>>,
): void {
  if (event.generationId !== generationId) {
    return;
  }

  setPendingRequest((current) => {
    if (!current || current.generationId !== generationId) {
      return current;
    }
    if (event.type === "started") {
      return { ...current, status: "streaming" };
    }
    if (event.type === "delta" && event.content) {
      return {
        ...current,
        status: "streaming",
        assistantContent: current.assistantContent + event.content,
      };
    }
    return current;
  });
}
