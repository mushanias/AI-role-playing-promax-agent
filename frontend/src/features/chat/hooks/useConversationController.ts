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
  GenerationSnapshot,
  PendingRequest,
} from "../model/types";
import { ApiRequestError } from "../../../shared/api/ApiClient";
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
  refresh(): Promise<void>;
  dismissError(): void;
}

const PENDING_GENERATION_KEY = "versioned-chat.pending-generation";
const GENERATION_POLL_INTERVAL_MS = 400;
const GENERATION_RETRY_INTERVAL_MS = 1_000;

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
    readPendingRequest,
  );
  const [failedRequestContent, setFailedRequestContent] = useState<
    string | null
  >(null);
  const [editingTurnId, setEditingTurnId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState("");
  const activeConversationIdRef = useRef<string | null>(null);
  const pendingRequestRef = useRef<PendingRequest | null>(pendingRequest);

  useEffect(() => {
    activeConversationIdRef.current = view?.conversationId ?? null;
  }, [view]);

  useEffect(() => {
    pendingRequestRef.current = pendingRequest;
    try {
      if (pendingRequest === null) {
        window.sessionStorage.removeItem(PENDING_GENERATION_KEY);
      } else {
        window.sessionStorage.setItem(
          PENDING_GENERATION_KEY,
          JSON.stringify(pendingRequest),
        );
      }
    } catch {
      // 存储不可用时仍保持当前页面内的轮询，不影响生成流程。
    }
  }, [pendingRequest]);

  const loadConversationData = useCallback(
    async (showInitialLoading: boolean): Promise<void> => {
      if (showInitialLoading) {
        setIsLoading(true);
      }
      try {
        const [nextView, conversations, deletedConversations] =
          await Promise.all([
            gateway.getConversation(),
            gateway.listConversations(),
            gateway.listDeletedConversations(),
          ]);
        setView(nextView);
        setConversationList(conversations);
        setDeletedConversationList(deletedConversations);
        setError(null);
      } catch (reason: unknown) {
        setError(toUserFacingError(reason));
      } finally {
        if (showInitialLoading) {
          setIsLoading(false);
        }
      }
    },
    [gateway],
  );

  const refresh = useCallback(
    () => loadConversationData(false),
    [loadConversationData],
  );

  useEffect(() => {
    void loadConversationData(true);
  }, [loadConversationData]);

  useEffect(() => {
    const resume = () => {
      if (
        document.visibilityState === "visible" &&
        pendingRequestRef.current === null
      ) {
        void refresh();
      }
    };

    document.addEventListener("visibilitychange", resume);
    window.addEventListener("pageshow", resume);
    return () => {
      document.removeEventListener("visibilitychange", resume);
      window.removeEventListener("pageshow", resume);
    };
  }, [refresh]);

  useEffect(() => {
    const generationId = pendingRequest?.generationId;
    const requestContent = pendingRequest?.content ?? null;
    if (!generationId) {
      return;
    }

    let isActive = true;
    void pollGeneration(
      gateway,
      generationId,
      () => isActive,
      (snapshot) => {
        if (isActive) {
          applyGenerationSnapshot(snapshot, generationId, setPendingRequest);
        }
      },
    )
      .then(async () => {
        if (isActive) {
          await refresh();
        }
      })
      .catch(async (reason: unknown) => {
        if (!isActive) {
          return;
        }
        await refresh();
        if (isActive) {
          setError(toUserFacingError(reason));
          setFailedRequestContent(requestContent);
        }
      })
      .finally(() => {
        if (isActive) {
          setPendingRequest((current) =>
            current?.generationId === generationId ? null : current,
          );
        }
      });

    return () => {
      isActive = false;
    };
  }, [gateway, pendingRequest?.generationId, refresh]);

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
      isSubmitting ||
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
    setIsSubmitting(true);

    try {
      await gateway.startRewriteGeneration({
        conversationId: view.conversationId,
        sourceBranchId: view.activeBranchId,
        turnId: editingTurnId,
        content: normalizedContent,
        generationId,
      });
      setPendingRequest({
        conversationId: view.conversationId,
        generationId,
        content: normalizedContent,
        assistantContent: "",
        startedAt: Date.now(),
        status: "starting",
      });
    } catch (reason: unknown) {
      if (activeConversationIdRef.current === view.conversationId) {
        setView(sourceView);
        setError(toUserFacingError(reason));
        setFailedRequestContent(normalizedContent);
      }
    } finally {
      setIsSubmitting(false);
    }
  }, [
    editingContent,
    editingTurnId,
    gateway,
    isSubmitting,
    pendingRequest,
    view,
  ]);

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
      setIsSubmitting(true);

      let targetConversationId: string | null = null;
      const generationId = crypto.randomUUID();
      try {
        const targetView = view ?? (await gateway.createConversation());
        targetConversationId = targetView.conversationId;
        if (!view) {
          activeConversationIdRef.current = targetView.conversationId;
          setView(targetView);
        }
        await gateway.startMessageGeneration({
          conversationId: targetView.conversationId,
          branchId: targetView.activeBranchId,
          content: normalizedContent,
          generationId,
        });
        setPendingRequest({
          conversationId: targetView.conversationId,
          generationId,
          content: normalizedContent,
          assistantContent: "",
          startedAt: Date.now(),
          status: "starting",
        });
      } catch (reason: unknown) {
        if (
          targetConversationId !== null &&
          activeConversationIdRef.current === targetConversationId
        ) {
          setError(toUserFacingError(reason));
          setFailedRequestContent(normalizedContent);
        }
      } finally {
        setIsSubmitting(false);
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
    refresh,
    dismissError: () => {
      setError(null);
      setFailedRequestContent(null);
    },
  };
}

async function pollGeneration(
  gateway: ConversationGateway,
  generationId: string,
  isActive: () => boolean,
  onSnapshot: (snapshot: GenerationSnapshot) => void,
): Promise<void> {
  while (isActive()) {
    await waitUntilPageVisible();
    if (!isActive()) {
      return;
    }

    let snapshot: GenerationSnapshot;
    try {
      snapshot = await gateway.getGeneration(generationId);
    } catch (reason: unknown) {
      if (reason instanceof ApiRequestError && reason.status === 0) {
        await delay(GENERATION_RETRY_INTERVAL_MS);
        continue;
      }
      throw reason;
    }

    onSnapshot(snapshot);
    if (snapshot.status === "failed") {
      throw new ApiRequestError(
        snapshot.message ?? "回答生成失败",
        snapshot.errorStatus ?? 500,
        snapshot.code,
      );
    }
    if (snapshot.status === "completed" || snapshot.status === "stopped") {
      return;
    }

    await delay(GENERATION_POLL_INTERVAL_MS);
  }
}

function applyGenerationSnapshot(
  snapshot: GenerationSnapshot,
  generationId: string,
  setPendingRequest: Dispatch<SetStateAction<PendingRequest | null>>,
): void {
  if (snapshot.generationId !== generationId) {
    return;
  }

  setPendingRequest((current) => {
    if (!current || current.generationId !== generationId) {
      return current;
    }
    return {
      ...current,
      status:
        snapshot.status === "starting"
          ? "starting"
          : snapshot.status === "stopped"
            ? "stopping"
            : "streaming",
      assistantContent: snapshot.content,
    };
  });
}

function waitUntilPageVisible(): Promise<void> {
  if (document.visibilityState === "visible") {
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    const resume = () => {
      if (document.visibilityState !== "visible") {
        return;
      }
      document.removeEventListener("visibilitychange", resume);
      window.removeEventListener("pageshow", resume);
      resolve();
    };
    document.addEventListener("visibilitychange", resume);
    window.addEventListener("pageshow", resume);
  });
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

function readPendingRequest(): PendingRequest | null {
  try {
    const raw = window.sessionStorage.getItem(PENDING_GENERATION_KEY);
    if (!raw) {
      return null;
    }
    const value = JSON.parse(raw) as Partial<PendingRequest>;
    if (
      typeof value.conversationId !== "string" ||
      typeof value.generationId !== "string" ||
      typeof value.content !== "string" ||
      typeof value.assistantContent !== "string" ||
      typeof value.startedAt !== "number" ||
      !["starting", "streaming", "stopping"].includes(value.status ?? "")
    ) {
      return null;
    }
    return value as PendingRequest;
  } catch {
    return null;
  }
}
