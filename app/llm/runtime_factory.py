"""按请求创建模型客户端的运行时工厂。"""

from app.exceptions import InvalidLLMConfigurationError
from app.llm.client import LLMClient
from app.llm.contracts import (
    LLMGenerateRequest,
    LLMGenerateResult,
    LLMProviderAdapter,
    LLMUsage,
    ProviderCapabilities,
    WebSearchPolicy,
)
from app.llm.settings import MODEL_SETTINGS, build_llm_model


class SDKLLMAdapter:
    """把现有 SDK 客户端适配为学习产品使用的统一契约。"""

    def __init__(
        self,
        provider: str,
        model: str,
        capabilities: ProviderCapabilities,
        client: LLMClient,
    ) -> None:
        self.provider = provider
        self.model = model
        self._capabilities = capabilities
        self.client = client

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    async def generate(
        self,
        request: LLMGenerateRequest,
    ) -> LLMGenerateResult:
        """执行普通模型调用；原生搜索由对应厂商适配器后续扩展。"""
        warnings: tuple[str, ...] = ()
        if request.web_search != WebSearchPolicy.DISABLED:
            if not self.capabilities.supports_native_search:
                if request.web_search == WebSearchPolicy.REQUIRED:
                    raise InvalidLLMConfigurationError(
                        f"{self.provider} 当前不支持原生联网搜索"
                    )
                warnings = ("当前模型不支持联网搜索，已使用普通回答",)
            else:
                warnings = ("当前厂商适配器尚未启用原生联网搜索",)

        reply = await self.client.chat(
            [
                {
                    "role": message.role.value,
                    "content": message.content,
                }
                for message in request.messages
            ]
        )
        return LLMGenerateResult(
            content=reply,
            provider=self.provider,
            model=self.model,
            usage=LLMUsage(),
            warnings=warnings,
        )


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
        return SDKLLMAdapter(
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
