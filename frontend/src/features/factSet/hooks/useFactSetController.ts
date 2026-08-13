import { useCallback, useEffect, useState } from "react";

import type { FactSetGateway } from "../services/FactSetGateway";

export interface FactSetController {
  content: string;
  isLoading: boolean;
  isSaving: boolean;
  statusMessage: string | null;
  save(content: string): Promise<boolean>;
}

export function useFactSetController(
  gateway: FactSetGateway,
  backendConnected: boolean,
): FactSetController {
  const [content, setContent] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!backendConnected) {
      setIsLoading(false);
      return () => {
        active = false;
      };
    }

    setIsLoading(true);
    setStatusMessage(null);
    gateway
      .get()
      .then((factSet) => {
        if (active) {
          setContent(factSet.content);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setStatusMessage(toErrorMessage(error, "读取设定失败"));
        }
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [backendConnected, gateway]);

  const save = useCallback(
    async (nextContent: string): Promise<boolean> => {
      setIsSaving(true);
      setStatusMessage(null);
      try {
        const factSet = await gateway.replace(nextContent);
        setContent(factSet.content);
        return true;
      } catch (error: unknown) {
        setStatusMessage(toErrorMessage(error, "保存设定失败"));
        return false;
      } finally {
        setIsSaving(false);
      }
    },
    [gateway],
  );

  return {
    content,
    isLoading,
    isSaving,
    statusMessage,
    save,
  };
}

function toErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
