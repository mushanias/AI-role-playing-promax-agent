import { apiRequest } from "../../../shared/api/ApiClient";
import type {
  ActivateLLMInput,
  ActiveLLMModel,
  LLMActivationResult,
  LLMPresetCatalog,
  SwitchLLMModelInput,
} from "../model/types";
import type { LLMGateway } from "./LLMGateway";

interface LLMPresetCatalogDto {
  default_provider: string;
  default_model: string;
  providers: Array<{
    id: string;
    name: string;
    models: string[];
    default_model: string;
    docs_url: string;
  }>;
}

interface ActiveLLMModelDto {
  provider: string;
  model: string;
  configured: boolean;
  verified: boolean;
}

interface LLMActivationDto {
  success: boolean;
  message: string;
  provider: string;
  model: string;
}

export class HttpLLMGateway implements LLMGateway {
  async getPresets(): Promise<LLMPresetCatalog> {
    const catalog = await apiRequest<LLMPresetCatalogDto>("/llm/presets", {
      timeoutMs: 5_000,
    });

    return {
      defaultProvider: catalog.default_provider,
      defaultModel: catalog.default_model,
      providers: catalog.providers.map((provider) => ({
        providerId: provider.id,
        name: provider.name,
        models: provider.models,
        defaultModel: provider.default_model,
        docsUrl: provider.docs_url,
      })),
    };
  }

  async getActiveModel(): Promise<ActiveLLMModel> {
    const active = await apiRequest<ActiveLLMModelDto>("/llm/active", {
      timeoutMs: 5_000,
    });
    return {
      providerId: active.provider,
      modelId: active.model,
      configured: active.configured,
      verified: active.verified,
    };
  }

  async verifyActiveModel(): Promise<LLMActivationResult> {
    const result = await apiRequest<LLMActivationDto>("/llm/active/verify", {
      method: "POST",
    });

    return {
      success: result.success,
      message: result.message,
      providerId: result.provider,
      modelId: result.model,
      configured: true,
      verified: result.success,
    };
  }

  async activateModel(
    input: ActivateLLMInput,
  ): Promise<LLMActivationResult> {
    const result = await apiRequest<LLMActivationDto>("/llm/active", {
      method: "PUT",
      body: JSON.stringify({
        api_key: input.apiKey,
        provider: input.providerId,
        model: input.modelId,
      }),
    });

    return {
      success: result.success,
      message: result.message,
      providerId: result.provider,
      modelId: result.model,
      configured: true,
      verified: result.success,
    };
  }

  async switchActiveModel(
    input: SwitchLLMModelInput,
  ): Promise<LLMActivationResult> {
    const result = await apiRequest<LLMActivationDto>("/llm/active/model", {
      method: "PUT",
      body: JSON.stringify({
        provider: input.providerId,
        model: input.modelId,
      }),
    });

    return {
      success: result.success,
      message: result.message,
      providerId: result.provider,
      modelId: result.model,
      configured: true,
      verified: result.success,
    };
  }
}
