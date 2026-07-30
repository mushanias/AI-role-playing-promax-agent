"""按请求创建模型客户端的运行时工厂。"""

"""按请求创建模型客户端的运行时工厂。"""

from app.exceptions import InvalidLLMConfigurationError
from app.llm.client import LLMClient
from app.llm.contracts import (
    LLMProviderAdapter,
    ProviderCapabilities,
)
from app.llm.providers import (
    AnthropicSearchAdapter,
    GLMSearchAdapter,
    OpenAIResponsesSearchAdapter,
    PlainLLMAdapter,
)
from app.llm.settings import MODEL_SETTINGS, build_llm_model


ADAPTER_TYPES = {
    "openai": OpenAIResponsesSearchAdapter,
    "xai": OpenAIResponsesSearchAdapter,
    "anthropic": AnthropicSearchAdapter,
    "glm": GLMSearchAdapter,
}


class RuntimeLLMFactory:
    """为每次请求创建独立客户端，避免 API Key 进入全局状态。"""

    def create(
        self,
        provider: str,
        model: str,
        api_key: str,
    ) -> LLMProviderAdapter:
        """根据内置厂商目录创建调用专用适配器。"""
        if not api_key:
            raise InvalidLLMConfigurationError("API Key 不能为空")

        try:
            setting = MODEL_SETTINGS[provider]
        except KeyError:
            raise InvalidLLMConfigurationError(
                f"未知的模型厂商：{provider}"
            ) from None

        model_setting = build_llm_model(
            api_key=api_key,
            provider=provider,
            model=model,
        )
        capabilities = ProviderCapabilities(
            provider=provider,
            supported_models=tuple(setting["models"]),
            supports_native_search=setting["supports_native_search"],
            context_window=setting["context_window"],
            max_output_tokens=_max_output_tokens(setting),
        )
        adapter_type = ADAPTER_TYPES.get(provider, PlainLLMAdapter)
        return adapter_type(
            provider=provider,
            model=model,
            capabilities=capabilities,
            client=LLMClient(model_setting),
        )


def _max_output_tokens(setting: dict) -> int:
    request = setting["request_params"]
    return int(
        request.get("max_output_tokens", request.get("max_tokens", 4096))
    )
