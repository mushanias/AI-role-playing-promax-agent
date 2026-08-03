import type {
  ActivateLLMInput,
  ActiveLLMModel,
  LLMActivationResult,
  LLMPresetCatalog,
} from "../model/types";

export interface LLMGateway {
  getPresets(): Promise<LLMPresetCatalog>;
  getActiveModel(): Promise<ActiveLLMModel>;
  activateModel(input: ActivateLLMInput): Promise<LLMActivationResult>;
}
