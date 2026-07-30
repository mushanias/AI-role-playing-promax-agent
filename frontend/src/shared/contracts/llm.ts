/** 模型目录与连接测试契约。 */

export interface LLMProvider {
  id: string;
  name: string;
  models: string[];
  default_model: string;
  docs_url: string;
  supports_native_search: boolean;
  context_window: number;
}

export interface LLMPresetList {
  default_provider: string;
  default_model: string;
  providers: LLMProvider[];
}

export interface LLMConnectionResult {
  success: boolean;
  message: string;
}
