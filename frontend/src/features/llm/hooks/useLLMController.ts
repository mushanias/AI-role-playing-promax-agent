import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type {
  ActiveLLMModel,
  LLMActivationResult,
  LLMProviderPreset,
  LLMProviderState,
} from "../model/types";
import type { LLMGateway } from "../services/LLMGateway";

export interface LLMController {
  providers: LLMProviderState[];
  activeProviderId: string;
  activeModelId: string;
  isLoading: boolean;
  isUpdating: boolean;
  statusMessage: string | null;
  selectModel(providerId: string, modelId: string): Promise<boolean>;
  connectProvider(
    providerId: string,
    modelId: string,
    apiKey: string,
  ): Promise<boolean>;
  verifyLocalConfig(): Promise<boolean>;
}

export function useLLMController(
  gateway: LLMGateway,
  backendConnected: boolean,
): LLMController {
  const [providerPresets, setProviderPresets] = useState<LLMProviderPreset[]>(
    [],
  );
  const [activeModel, setActiveModel] = useState<ActiveLLMModel | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const apiKeysRef = useRef(new Map<string, string>());

  useEffect(() => {
    let isActive = true;

    if (!backendConnected) {
      setProviderPresets([]);
      setActiveModel(null);
      setIsLoading(false);
      setStatusMessage("本地后端未连接");
      return () => {
        isActive = false;
      };
    }

    setIsLoading(true);
    setStatusMessage(null);

    Promise.all([gateway.getPresets(), gateway.getActiveModel()])
      .then(([catalog, currentModel]) => {
        if (!isActive) {
          return;
        }

        setProviderPresets(catalog.providers);
        setActiveModel(currentModel);
        setStatusMessage(null);
      })
      .catch((error: unknown) => {
        if (isActive) {
          setStatusMessage(toErrorMessage(error));
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
  }, [backendConnected, gateway]);

  const providers = useMemo<LLMProviderState[]>(
    () =>
      providerPresets.map((provider) => {
        const active = provider.providerId === activeModel?.providerId;
        return {
          ...provider,
          active,
          configured:
            (active && Boolean(activeModel?.configured)) ||
            apiKeysRef.current.has(provider.providerId),
          verified: active && Boolean(activeModel?.verified),
        };
      }),
    [activeModel, providerPresets],
  );

  const applySuccessfulActivation = useCallback(
    (result: LLMActivationResult) => {
      setActiveModel({
        providerId: result.providerId,
        modelId: result.modelId,
        configured: result.configured,
        verified: result.verified,
      });
    },
    [],
  );

  const selectModel = useCallback(
    async (providerId: string, modelId: string): Promise<boolean> => {
      const provider = providerPresets.find(
        (candidate) => candidate.providerId === providerId,
      );
      if (!provider?.models.includes(modelId)) {
        setStatusMessage("所选模型不在后端模型目录中");
        return false;
      }

      const canReuseBackendKey =
        activeModel?.providerId === providerId && activeModel.configured;
      const cachedApiKey = apiKeysRef.current.get(providerId);
      if (!canReuseBackendKey && !cachedApiKey) {
        setStatusMessage(`请先连接 ${provider.name} 的 API Key`);
        return false;
      }

      setIsUpdating(true);
      setStatusMessage("正在切换模型…");

      try {
        const result = canReuseBackendKey
          ? await gateway.switchActiveModel({ providerId, modelId })
          : await gateway.activateModel({
              apiKey: cachedApiKey ?? "",
              providerId,
              modelId,
            });

        setStatusMessage(result.message);
        if (result.success) {
          applySuccessfulActivation(result);
        }
        return result.success;
      } catch (error: unknown) {
        setStatusMessage(toErrorMessage(error));
        return false;
      } finally {
        setIsUpdating(false);
      }
    },
    [activeModel, applySuccessfulActivation, gateway, providerPresets],
  );

  const connectProvider = useCallback(
    async (
      providerId: string,
      modelId: string,
      apiKey: string,
    ): Promise<boolean> => {
      const provider = providerPresets.find(
        (candidate) => candidate.providerId === providerId,
      );
      const normalizedApiKey = apiKey.trim();

      if (!provider?.models.includes(modelId) || !normalizedApiKey) {
        return false;
      }

      setIsUpdating(true);
      setStatusMessage(`正在验证 ${provider.name}…`);

      try {
        const result = await gateway.activateModel({
          apiKey: normalizedApiKey,
          providerId,
          modelId,
        });
        setStatusMessage(result.message);

        if (result.success) {
          apiKeysRef.current.set(providerId, normalizedApiKey);
          applySuccessfulActivation(result);
        }
        return result.success;
      } catch (error: unknown) {
        setStatusMessage(toErrorMessage(error));
        return false;
      } finally {
        setIsUpdating(false);
      }
    },
    [applySuccessfulActivation, gateway, providerPresets],
  );

  const verifyLocalConfig = useCallback(async (): Promise<boolean> => {
    setIsUpdating(true);
    setStatusMessage("正在验证后端本地配置…");

    try {
      const result = await gateway.verifyActiveModel();
      setActiveModel({
        providerId: result.providerId,
        modelId: result.modelId,
        configured: result.configured,
        verified: result.verified,
      });
      setStatusMessage(result.message);
      return result.success;
    } catch (error: unknown) {
      setStatusMessage(toErrorMessage(error));
      return false;
    } finally {
      setIsUpdating(false);
    }
  }, [gateway]);

  return {
    providers,
    activeProviderId: activeModel?.providerId ?? "",
    activeModelId: activeModel?.modelId ?? "",
    isLoading,
    isUpdating,
    statusMessage,
    selectModel,
    connectProvider,
    verifyLocalConfig,
  };
}

function toErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "模型配置请求失败";
}
