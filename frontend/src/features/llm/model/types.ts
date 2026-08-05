export interface LLMProviderPreset {
  providerId: string;
  name: string;
  models: string[];
  defaultModel: string;
  docsUrl: string;
}

export interface LLMProviderState extends LLMProviderPreset {
  active: boolean;
  configured: boolean;
  verified: boolean;
}

export interface LLMPresetCatalog {
  defaultProvider: string;
  defaultModel: string;
  providers: LLMProviderPreset[];
}

export interface ActiveLLMModel {
  providerId: string;
  modelId: string;
  configured: boolean;
  verified: boolean;
}

export interface ActivateLLMInput {
  apiKey: string;
  providerId: string;
  modelId: string;
}

export interface SwitchLLMModelInput {
  providerId: string;
  modelId: string;
}

export interface LLMActivationResult extends ActiveLLMModel {
  success: boolean;
  message: string;
}
