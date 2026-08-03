export interface LLMProviderPreset {
  providerId: string;
  name: string;
  models: string[];
  defaultModel: string;
  docsUrl: string;
}

export interface LLMPresetCatalog {
  defaultProvider: string;
  defaultModel: string;
  providers: LLMProviderPreset[];
}

export interface ActiveLLMModel {
  providerId: string;
  modelId: string;
  connected: boolean;
}

export interface ActivateLLMInput {
  apiKey: string;
  providerId: string;
  modelId: string;
}

export interface LLMActivationResult extends ActiveLLMModel {
  success: boolean;
  message: string;
}
