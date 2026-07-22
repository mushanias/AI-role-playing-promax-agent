"""统一 LLM 客户端：适配 OpenAI 与 Anthropic SDK（异步）。"""

import logging
import time
from typing import Dict, List

import anthropic
import openai

from app.exceptions import LLMAuthError, LLMNetworkError, LLMResponseError
from app.llm import LLMModel

logger = logging.getLogger(__name__)


class LLMClient:
    """通过统一的 chat 接口调用不同 SDK。"""

    def __init__(self, model: LLMModel) -> None:
        """按照模型配置初始化对应的异步 SDK 客户端。"""
        self.model = model
        if model.adapter == "anthropic":
            self.client = anthropic.AsyncAnthropic(
                api_key=model.api_key,
                base_url=model.base_url,
            )
        else:
            self.client = openai.AsyncOpenAI(
                api_key=model.api_key,
                base_url=model.base_url,
            )
        logger.debug(
            "LLM 客户端初始化完成，SDK: %s，模型: %s",
            model.adapter,
            model.model,
        )

    async def chat(self, messages: List[Dict]) -> str:
        """调用当前模型并返回纯文本回复。"""
        msg_count = len(messages)
        total_chars = sum(len(message["content"]) for message in messages)
        logger.debug("调用 LLM：%s 条消息，共 %s 字", msg_count, total_chars)

        start_time = time.time()
        if self.model.adapter == "anthropic":
            reply = await self._chat_anthropic(messages)
        elif self.model.adapter == "openai_responses":
            reply = await self._chat_openai_responses(messages)
        else:
            reply = await self._chat_openai(messages)

        if not reply:
            raise LLMResponseError("LLM 返回了空回复")

        elapsed = time.time() - start_time
        logger.info("LLM 回复完成：耗时 %.2fs，回复 %s 字", elapsed, len(reply))
        return reply

    async def _chat_openai(self, messages: List[Dict]) -> str:
        """调用 OpenAI 兼容接口。"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model.model,
                messages=messages,
            )
        except openai.AuthenticationError:
            raise LLMAuthError(
                "API Key 错误或失效，请检查当前模型的 LLM_API_KEY"
            ) from None
        except (openai.APIConnectionError, openai.APITimeoutError):
            raise LLMNetworkError("网络连接失败或超时，请检查网络") from None
        except openai.RateLimitError:
            raise LLMNetworkError(
                "LLM 服务繁忙或请求频率过高，请稍后重试"
            ) from None
        except openai.BadRequestError as error:
            raise LLMResponseError(
                f"LLM 拒绝了本次请求：{error.message}"
            ) from None
        except openai.APIStatusError as error:
            raise LLMResponseError(
                f"LLM 服务返回异常状态：{error.status_code}"
            ) from None

        if not response.choices:
            raise LLMResponseError("LLM 返回结果中没有候选回复")
        return response.choices[0].message.content or ""

    async def _chat_openai_responses(self, messages: List[Dict]) -> str:
        """调用 OpenAI Responses 兼容接口。"""
        try:
            response = await self.client.responses.create(
                model=self.model.model,
                input=messages,
                max_output_tokens=self.model.max_tokens,
            )
        except openai.AuthenticationError:
            raise LLMAuthError(
                "API Key 错误或失效，请检查当前模型的 API Key"
            ) from None
        except (openai.APIConnectionError, openai.APITimeoutError):
            raise LLMNetworkError("网络连接失败或超时，请检查网络") from None
        except openai.RateLimitError:
            raise LLMNetworkError(
                "LLM 服务繁忙或请求频率过高，请稍后重试"
            ) from None
        except openai.BadRequestError as error:
            raise LLMResponseError(
                f"LLM 拒绝了本次请求：{error.message}"
            ) from None
        except openai.APIStatusError as error:
            raise LLMResponseError(
                f"LLM 服务返回异常状态：{error.status_code}"
            ) from None

        return response.output_text or ""

    async def _chat_anthropic(self, messages: List[Dict]) -> str:
        """调用 Anthropic 兼容接口，并适配 system 与内容块格式。"""
        system_parts = [
            message["content"]
            for message in messages
            if message["role"] == "system"
        ]
        chat_messages = [
            message
            for message in messages
            if message["role"] != "system"
        ]
        request = {
            "model": self.model.model,
            "max_tokens": self.model.max_tokens,
            "messages": chat_messages,
        }
        if system_parts:
            request["system"] = "\n\n".join(system_parts)

        try:
            response = await self.client.messages.create(**request)
        except anthropic.AuthenticationError:
            raise LLMAuthError(
                "API Key 错误或失效，请检查当前模型的 LLM_API_KEY"
            ) from None
        except (anthropic.APIConnectionError, anthropic.APITimeoutError):
            raise LLMNetworkError("网络连接失败或超时，请检查网络") from None
        except anthropic.RateLimitError:
            raise LLMNetworkError(
                "LLM 服务繁忙或请求频率过高，请稍后重试"
            ) from None
        except anthropic.BadRequestError as error:
            raise LLMResponseError(
                f"LLM 拒绝了本次请求：{error.message}"
            ) from None
        except anthropic.APIStatusError as error:
            raise LLMResponseError(
                f"LLM 服务返回异常状态：{error.status_code}"
            ) from None

        text_blocks = [
            block.text
            for block in response.content
            if block.type == "text"
        ]
        return "".join(text_blocks)
