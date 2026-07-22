"""LLM 模型参数表与统一出口。"""

import os
from copy import deepcopy
from typing import Any, Literal

from dotenv import load_dotenv

from app.exceptions import InvalidLLMConfigurationError


load_dotenv()

LLMSDK = Literal["openai_chat", "openai_responses", "anthropic"]
LLMModel = dict[str, Any]


# 每项都按对应 SDK 的参数名称填写。
# client_params 直接传给 SDK 客户端，request_params 直接传给模型请求。
MODEL_SETTINGS: dict[str, LLMModel] = {
    "deepseek": {
        "name": "DeepSeek",
        "sdk": "openai_chat",
        "models": ("deepseek-v4-flash", "deepseek-v4-pro"),
        "docs_url": "https://api-docs.deepseek.com/",
        "client_params": {
            "base_url": "https://api.deepseek.com",
        },
        "request_params": {
            "model": "deepseek-v4-flash",
            "max_tokens": 4096,
        },
    },
    "openai": {
        "name": "GPT / OpenAI",
        "sdk": "openai_responses",
        "models": ("gpt-5.6", "gpt-5.6-terra", "gpt-5.6-luna"),
        "docs_url": "https://developers.openai.com/api/docs/models/all",
        "client_params": {
            "base_url": "https://api.openai.com/v1",
        },
        "request_params": {
            "model": "gpt-5.6",
            "max_output_tokens": 4096,
        },
    },
    "anthropic": {
        "name": "Claude / Anthropic",
        "sdk": "anthropic",
        "models": (
            "claude-opus-4-8",
            "claude-sonnet-5",
            "claude-haiku-4-5",
        ),
        "docs_url": (
            "https://platform.claude.com/docs/en/about-claude/models/overview"
        ),
        "client_params": {
            "base_url": "https://api.anthropic.com",
        },
        "request_params": {
            "model": "claude-sonnet-5",
            "max_tokens": 4096,
        },
    },
    "xai": {
        "name": "Grok / xAI",
        "sdk": "openai_responses",
        "models": ("grok-4.5",),
        "docs_url": "https://docs.x.ai/developers/models",
        "client_params": {
            "base_url": "https://api.x.ai/v1",
        },
        "request_params": {
            "model": "grok-4.5",
            "max_output_tokens": 4096,
        },
    },
    "glm": {
        "name": "GLM / 智谱",
        "sdk": "openai_chat",
        "models": ("glm-5.2", "glm-4.7"),
        "docs_url": "https://docs.bigmodel.cn/cn/guide/models/text/glm-5",
        "client_params": {
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
        },
        "request_params": {
            "model": "glm-5.2",
            "max_tokens": 4096,
        },
    },
    "minimax": {
        "name": "MiniMax",
        "sdk": "anthropic",
        "models": ("MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.7-highspeed"),
        "docs_url": (
            "https://platform.minimaxi.com/docs/api-reference/text-chat-anthropic"
        ),
        "client_params": {
            "base_url": "https://api.minimaxi.com/anthropic",
        },
        "request_params": {
            "model": "MiniMax-M3",
            "max_tokens": 4096,
        },
    },
}

DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "minimax")
if DEFAULT_LLM_PROVIDER not in MODEL_SETTINGS:
    raise InvalidLLMConfigurationError(
        f"未知的默认模型厂商：{DEFAULT_LLM_PROVIDER}"
    )

DEFAULT_LLM_MODEL = os.getenv(
    "DEFAULT_LLM_MODEL",
    MODEL_SETTINGS[DEFAULT_LLM_PROVIDER]["request_params"]["model"],
)


def build_llm_model(
    api_key: str,
    provider: str | None = None,
    model: str | None = None,
    custom_setting: dict[str, Any] | None = None,
) -> LLMModel:
    """选择一份参数，填入 API Key 和模型名称后返回给下游。"""
    selected_provider = provider or DEFAULT_LLM_PROVIDER

    if custom_setting is not None:
        setting = deepcopy(custom_setting)
        setting.setdefault("provider", setting.get("name", "custom"))
    else:
        try:
            setting = deepcopy(MODEL_SETTINGS[selected_provider])
        except KeyError:
            raise InvalidLLMConfigurationError(
                f"未知的模型厂商：{selected_provider}"
            ) from None

        selected_model = model or setting["request_params"]["model"]
        if selected_model not in setting["models"]:
            raise InvalidLLMConfigurationError(
                f"{setting['name']} 不支持模型：{selected_model}"
            )
        setting["provider"] = selected_provider
        setting["request_params"]["model"] = selected_model

    setting["client_params"]["api_key"] = api_key
    return setting


llm_model = build_llm_model(
    api_key=os.getenv("LLM_API_KEY", ""),
    provider=DEFAULT_LLM_PROVIDER,
    model=DEFAULT_LLM_MODEL,
)
