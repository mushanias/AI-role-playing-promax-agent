import type {
  ConversationCommand,
  ConversationDelta,
} from "../../../shared/contracts/learning";
import type {
  LLMConnectionResult,
  LLMPresetList,
} from "../../../shared/contracts/llm";

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

/** 前端唯一的后端 HTTP 出口，组件不直接调用 fetch。 */
export class LearningApiClient {
  constructor(private readonly baseUrl = "/api") {}

  async listModelPresets(): Promise<LLMPresetList> {
    return this.request<LLMPresetList>("/llm/presets");
  }

  async testConnection(input: {
    apiKey: string;
    provider: string;
    model: string;
  }): Promise<LLMConnectionResult> {
    return this.request<LLMConnectionResult>("/llm/connection-test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: input.apiKey,
        provider: input.provider,
        model: input.model,
      }),
    });
  }

  async executeTurn(
    command: ConversationCommand,
    apiKey: string,
  ): Promise<ConversationDelta> {
    return this.request<ConversationDelta>(
      "/learning/conversations/turns",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Provider-API-Key": apiKey,
        },
        body: JSON.stringify(command),
      },
    );
  }

  private async request<Result>(
    path: string,
    init?: RequestInit,
  ): Promise<Result> {
    const response = await fetch(`${this.baseUrl}${path}`, init);
    if (response.ok) {
      return (await response.json()) as Result;
    }
    const payload = (await response.json().catch(() => null)) as {
      error?: { code?: string; message?: string };
      detail?: string;
    } | null;
    throw new ApiRequestError(
      payload?.error?.message ??
        payload?.detail ??
        `请求失败（${response.status}）`,
      response.status,
      payload?.error?.code,
    );
  }
}
