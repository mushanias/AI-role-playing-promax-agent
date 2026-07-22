"""LLM 模型目录、默认选择与统一运行配置。"""

import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv

from app.exceptions import InvalidLLMConfigurationError


load_dotenv()

LLMAdapter = Literal[
    "openai_chat",
    "openai_responses",
    "anthropic",
]


@dataclass(frozen=True)
class LLMProviderPreset:
    """供模型选择界面展示和解析的厂商预设。"""

    provider: str
    name: str
    adapter: LLMAdapter
    base_url: str
    models: tuple[str, ...]
    default_model: str
    max_tokens: int
    docs_url: str

    def __post_init__(self) -> None:
        if self.default_model not in self.models:
            raise ValueError("默认模型必须位于支持模型列表中")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens 必须大于 0")


@dataclass(frozen=True)
class LLMModel:
    """下游实际使用的统一模型运行配置。"""

    provider: str
    adapter: LLMAdapter
    api_key: str
    base_url: str
    model: str
    max_tokens: int = 4096

    def __post_init__(self) -> None:
        if self.adapter not in {
            "openai_chat",
            "openai_responses",
            "anthropic",
        }:
            raise ValueError("不支持的 LLM 适配器")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens 必须大于 0")


MODEL_PRESETS: dict[str, LLMProviderPreset] = {
    "deepseek": LLMProviderPreset(
        provider="deepseek",
        name="DeepSeek",
        adapter="openai_chat",
        base_url="https://api.deepseek.com",
        models=("deepseek-v4-flash", "deepseek-v4-pro"),
        default_model="deepseek-v4-flash",
        max_tokens=4096,
        docs_url="https://api-docs.deepseek.com/",
    ),
    "openai": LLMProviderPreset(
        provider="openai",
        name="GPT / OpenAI",
        adapter="openai_responses",
        base_url="https://api.openai.com/v1",
        models=("gpt-5.6", "gpt-5.6-terra", "gpt-5.6-luna"),
        default_model="gpt-5.6",
        max_tokens=4096,
        docs_url="https://developers.openai.com/api/docs/models/all",
    ),
    "anthropic": LLMProviderPreset(
        provider="anthropic",
        name="Claude / Anthropic",
        adapter="anthropic",
        base_url="https://api.anthropic.com",
        models=(
            "claude-opus-4-8",
            "claude-sonnet-5",
            "claude-haiku-4-5",
        ),
        default_model="claude-sonnet-5",
        max_tokens=4096,
        docs_url=(
            "https://platform.claude.com/docs/en/about-claude/models/overview"
        ),
    ),
    "xai": LLMProviderPreset(
        provider="xai",
        name="Grok / xAI",
        adapter="openai_responses",
        base_url="https://api.x.ai/v1",
        models=("grok-4.5",),
        default_model="grok-4.5",
        max_tokens=4096,
        docs_url="https://docs.x.ai/developers/models",
    ),
    "glm": LLMProviderPreset(
        provider="glm",
        name="GLM / 智谱",
        adapter="openai_chat",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        models=("glm-5.2", "glm-4.7"),
        default_model="glm-5.2",
        max_tokens=4096,
        docs_url="https://docs.bigmodel.cn/cn/guide/models/text/glm-5",
    ),
    "minimax": LLMProviderPreset(
        provider="minimax",
        name="MiniMax",
        adapter="anthropic",
        base_url="https://api.minimaxi.com/anthropic",
        models=("MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.7-highspeed"),
        default_model="MiniMax-M3",
        max_tokens=4096,
        docs_url="https://platform.minimaxi.com/docs/api-reference/text-chat-anthropic",
    ),
}

DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "minimax")
try:
    _default_preset = MODEL_PRESETS[DEFAULT_LLM_PROVIDER]
except KeyError:
    raise InvalidLLMConfigurationError(
        f"未知的默认模型厂商：{DEFAULT_LLM_PROVIDER}"
    ) from None
DEFAULT_LLM_MODEL = os.getenv(
    "DEFAULT_LLM_MODEL",
    _default_preset.default_model,
)


def build_llm_model(
    provider: str,
    api_key: str,
    model: str | None = None,
) -> LLMModel:
    """从内置预设生成下游统一使用的模型配置。"""
    try:
        preset = MODEL_PRESETS[provider]
    except KeyError:
        raise InvalidLLMConfigurationError(
            f"未知的模型厂商：{provider}"
        ) from None

    selected_model = model or preset.default_model
    if selected_model not in preset.models:
        raise InvalidLLMConfigurationError(
            f"{preset.name} 不支持模型：{selected_model}"
        )
    return LLMModel(
        provider=preset.provider,
        adapter=preset.adapter,
        api_key=api_key,
        base_url=preset.base_url,
        model=selected_model,
        max_tokens=preset.max_tokens,
    )


def build_custom_llm_model(
    *,
    name: str,
    adapter: LLMAdapter,
    api_key: str,
    base_url: str,
    model: str,
    max_tokens: int = 4096,
) -> LLMModel:
    """从浏览器提交的自定义预设生成统一模型配置。"""
    return LLMModel(
        provider=name,
        adapter=adapter,
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        model=model,
        max_tokens=max_tokens,
    )


llm_model = build_llm_model(
    provider=DEFAULT_LLM_PROVIDER,
    model=DEFAULT_LLM_MODEL,
    api_key=os.getenv("LLM_API_KEY", ""),
)
