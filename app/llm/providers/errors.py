"""把厂商 SDK 异常转换为应用层稳定异常。"""

from collections.abc import Awaitable
from typing import TypeVar

import anthropic
import openai

from app.exceptions import LLMAuthError, LLMNetworkError, LLMResponseError

ResultType = TypeVar("ResultType")


async def call_openai(request: Awaitable[ResultType]) -> ResultType:
    """执行 OpenAI 兼容调用并隐藏厂商异常类型。"""
    try:
        return await request
    except openai.AuthenticationError:
        raise LLMAuthError("API Key 错误或失效，请检查当前厂商的 API Key") from None
    except (openai.APIConnectionError, openai.APITimeoutError):
        raise LLMNetworkError("网络连接失败或超时，请检查网络") from None
    except openai.RateLimitError:
        raise LLMNetworkError("LLM 服务繁忙或请求频率过高，请稍后重试") from None
    except openai.BadRequestError as error:
        raise LLMResponseError(f"LLM 拒绝了本次请求：{error.message}") from None
    except openai.APIStatusError as error:
        raise LLMResponseError(
            f"LLM 服务返回异常状态：{error.status_code}"
        ) from None


async def call_anthropic(request: Awaitable[ResultType]) -> ResultType:
    """执行 Anthropic 兼容调用并隐藏厂商异常类型。"""
    try:
        return await request
    except anthropic.AuthenticationError:
        raise LLMAuthError("API Key 错误或失效，请检查当前厂商的 API Key") from None
    except (anthropic.APIConnectionError, anthropic.APITimeoutError):
        raise LLMNetworkError("网络连接失败或超时，请检查网络") from None
    except anthropic.RateLimitError:
        raise LLMNetworkError("LLM 服务繁忙或请求频率过高，请稍后重试") from None
    except anthropic.BadRequestError as error:
        raise LLMResponseError(f"LLM 拒绝了本次请求：{error.message}") from None
    except anthropic.APIStatusError as error:
        raise LLMResponseError(
            f"LLM 服务返回异常状态：{error.status_code}"
        ) from None
