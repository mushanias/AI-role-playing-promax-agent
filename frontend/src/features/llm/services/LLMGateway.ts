import type {
  ActivateLLMInput,
  ActiveLLMModel,
  LLMActivationResult,
  LLMPresetCatalog,
  SwitchLLMModelInput,
} from "../model/types";

export interface LLMGateway {
  getPresets(): Promise<LLMPresetCatalog>;
  getActiveModel(): Promise<ActiveLLMModel>;
  verifyActiveModel(): Promise<LLMActivationResult>;
  activateModel(input: ActivateLLMInput): Promise<LLMActivationResult>;
  switchActiveModel(input: SwitchLLMModelInput): Promise<LLMActivationResult>;
}
