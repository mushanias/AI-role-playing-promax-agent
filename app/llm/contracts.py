"""模型能力、请求与结果的稳定契约。"""

from enum import Enum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class LLMRole(str, Enum):
    """统一消息角色。"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class WebSearchPolicy(str, Enum):
    """模型原生联网搜索的调用策略。"""

    DISABLED = "disabled"
    AUTO = "auto"
    REQUIRED = "required"


class LLMMessage(BaseModel):
    """上游传给模型适配器的统一消息。"""

    model_config = ConfigDict(extra="forbid")

    role: LLMRole
    content: str = Field(min_length=1)


class ProviderCapabilities(BaseModel):
    """前后端都可以读取的厂商能力描述。"""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    supported_models: tuple[str, ...]
    supports_native_search: bool
    context_window: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)


class LLMSource(BaseModel):
    """厂商原生搜索返回的统一来源。"""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    publisher: str | None = None


class LLMUsage(BaseModel):
    """不同厂商都能够归一化的 Token 使用量。"""

    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class LLMGenerateRequest(BaseModel):
    """一次非流式模型调用。"""

    model_config = ConfigDict(extra="forbid")

    messages: tuple[LLMMessage, ...]
    web_search: WebSearchPolicy = WebSearchPolicy.DISABLED


class LLMGenerateResult(BaseModel):
    """所有厂商适配器必须返回的统一结果。"""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)
    sources: tuple[LLMSource, ...] = ()
    usage: LLMUsage = Field(default_factory=LLMUsage)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    warnings: tuple[str, ...] = ()


class LLMProviderAdapter(Protocol):
    """应用层依赖的单次模型能力。"""

    @property
    def capabilities(self) -> ProviderCapabilities:
        """返回当前厂商和模型的能力。"""

    async def generate(
        self,
        request: LLMGenerateRequest,
    ) -> LLMGenerateResult:
        """执行一次非流式生成。"""


class LLMAdapterFactory(Protocol):
    """按当前请求创建模型适配器，不保存 API Key。"""

    def create(
        self,
        provider: str,
        model: str,
        api_key: str,
    ) -> LLMProviderAdapter:
        """创建当前调用专用的厂商适配器。"""

