import { useCallback, useEffect, useRef, useState } from "react";

import type { ModelOption } from "../../navigation/model/types";
import type { LLMGateway } from "../services/LLMGateway";

export interface LLMController {
  modelOptions: ModelOption[];
  selectedModelOptionId: string;
  isConnected: boolean;
  isLoading: boolean;
  isUpdating: boolean;
  statusMessage: string | null;
  selectModel(optionId: string): Promise<void>;
  connectApiKey(apiKey: string): Promise<boolean>;
}

export function useLLMController(
  gateway: LLMGateway,
  backendConnected: boolean,
): LLMController {
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([]);
  const [selectedModelOptionId, setSelectedModelOptionId] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const apiKeyRef = useRef<string | null>(null);

  useEffect(() => {
    let isActive = true;

    if (!backendConnected) {
      setModelOptions([]);
      setSelectedModelOptionId("");
      setIsConnected(false);
      setIsLoading(false);
      setStatusMessage("本地后端未连接");
      return () => {
        isActive = false;
      };
    }

    setIsLoading(true);
    setStatusMessage(null);

    Promise.all([gateway.getPresets(), gateway.getActiveModel()])
      .then(([catalog, activeModel]) => {
        if (!isActive) {
          return;
        }

        const options = catalog.providers.flatMap((provider) =>
          provider.models.map((modelId) => ({
            optionId: toOptionId(provider.providerId, modelId),
            providerId: provider.providerId,
            modelId,
            label: modelId,
            description: provider.name,
          })),
        );
        const activeOptionId = toOptionId(
          activeModel.providerId,
          activeModel.modelId,
        );
        const defaultOptionId = toOptionId(
          catalog.defaultProvider,
          catalog.defaultModel,
        );

        setModelOptions(options);
        setSelectedModelOptionId(
          options.some((option) => option.optionId === activeOptionId)
            ? activeOptionId
            : defaultOptionId,
        );
        setIsConnected(activeModel.connected);
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

  const activateSelection = useCallback(
    async (optionId: string, apiKey: string): Promise<boolean> => {
      const option = modelOptions.find(
        (candidate) => candidate.optionId === optionId,
      );

      if (!option) {
        setStatusMessage("所选模型不在后端模型目录中");
        return false;
      }

      setIsUpdating(true);
      setStatusMessage("正在测试连接…");

      try {
        const result = await gateway.activateModel({
          apiKey,
          providerId: option.providerId,
          modelId: option.modelId,
        });
        setIsConnected(result.success);
        setStatusMessage(result.message);
        return result.success;
      } catch (error: unknown) {
        setIsConnected(false);
        setStatusMessage(toErrorMessage(error));
        return false;
      } finally {
        setIsUpdating(false);
      }
    },
    [gateway, modelOptions],
  );

  const selectModel = useCallback(
    async (optionId: string) => {
      setSelectedModelOptionId(optionId);

      if (!apiKeyRef.current) {
        setIsConnected(false);
        setStatusMessage("已选择模型，请连接对应的 API Key");
        return;
      }

      await activateSelection(optionId, apiKeyRef.current);
    },
    [activateSelection],
  );

  const connectApiKey = useCallback(
    async (apiKey: string): Promise<boolean> => {
      const normalizedApiKey = apiKey.trim();

      if (!normalizedApiKey || !selectedModelOptionId) {
        return false;
      }

      const success = await activateSelection(
        selectedModelOptionId,
        normalizedApiKey,
      );

      if (success) {
        apiKeyRef.current = normalizedApiKey;
      }

      return success;
    },
    [activateSelection, selectedModelOptionId],
  );

  return {
    modelOptions,
    selectedModelOptionId,
    isConnected,
    isLoading,
    isUpdating,
    statusMessage,
    selectModel,
    connectApiKey,
  };
}

function toOptionId(providerId: string, modelId: string): string {
  return `${providerId}:${modelId}`;
}

function toErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "模型配置请求失败";
}
