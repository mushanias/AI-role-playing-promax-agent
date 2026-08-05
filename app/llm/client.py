"""把统一模型设置中的参数发送给对应 SDK。"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Dict, List

import anthropic
import openai

from app.exceptions import LLMAuthError, LLMNetworkError, LLMResponseError
from app.llm import LLMModel

logger = logging.getLogger(__name__)


class LLMClient:
    """下游统一使用的 LLM 客户端。"""

    def __init__(self, model: LLMModel) -> None:
        """按照 sdk 判断一次，其余参数直接来自模型设置字典。"""
        self._configuration_lock = asyncio.Lock()
        self.model = model
        self.client = self._build_sdk_client(model)
        self._connection_verified = False
        logger.debug(
            "LLM 客户端初始化完成，SDK: %s，模型: %s",
            model["sdk"],
            model["request_params"]["model"],
        )

    async def reconfigure(
        self,
        model: LLMModel,
        *,
        connection_verified: bool = False,
    ) -> None:
        """原子替换后续聊天与压缩共用的模型客户端。"""
        next_client = self._build_sdk_client(model)
        async with self._configuration_lock:
            self.model = model
            self.client = next_client
            self._connection_verified = connection_verified
        logger.info(
            "LLM 客户端已切换：厂商=%s，模型=%s",
            model.get("provider", "unknown"),
            model["request_params"]["model"],
        )

    def describe_active_model(self) -> dict[str, object]:
        """返回可安全暴露的活动模型信息，不包含 API Key。"""
        return {
            "provider": self.model.get("provider", "unknown"),
            "model": self.model["request_params"]["model"],
            "configured": bool(self.model["client_params"].get("api_key")),
            "verified": self._connection_verified,
        }

    async def set_connection_verified(self, verified: bool) -> None:
        """记录真实连接测试结果，不改变当前模型及其 API Key。"""
        async with self._configuration_lock:
            self._connection_verified = verified

    async def chat(self, messages: List[Dict]) -> str:
        """调用当前模型并返回纯文本回复。"""
        async with self._configuration_lock:
            return await self._chat_with_active_model(messages)

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
    ) -> AsyncIterator[str]:
        """使用当前模型逐段返回文本，并在整个生成期间保持配置稳定。"""
        async with self._configuration_lock:
            started_at = time.time()
            received_content = False

            if self.model["sdk"] == "anthropic":
                stream = self._stream_anthropic(messages)
            elif self.model["sdk"] == "openai_responses":
                stream = self._stream_openai_responses(messages)
            else:
                stream = self._stream_openai(messages)

            async for content in stream:
                if not content:
                    continue
                received_content = True
                yield content

            if not received_content:
                raise LLMResponseError("LLM 返回了空回复")

            logger.info(
                "LLM 流式回复完成：耗时 %.2fs",
                time.time() - started_at,
            )

    async def _chat_with_active_model(self, messages: List[Dict]) -> str:
        """在配置锁内使用一份稳定的模型设置完成请求。"""
        msg_count = len(messages)
        total_chars = sum(len(message["content"]) for message in messages)
        logger.debug("调用 LLM：%s 条消息，共 %s 字", msg_count, total_chars)

        start_time = time.time()
        if self.model["sdk"] == "anthropic":
            reply = await self._chat_anthropic(messages)
        elif self.model["sdk"] == "openai_responses":
            reply = await self._chat_openai_responses(messages)
        else:
            reply = await self._chat_openai(messages)

        if not reply:
            raise LLMResponseError("LLM 返回了空回复")

        elapsed = time.time() - start_time
        logger.info("LLM 回复完成：耗时 %.2fs，回复 %s 字", elapsed, len(reply))
        return reply

    @staticmethod
    def _build_sdk_client(model: LLMModel):
        if model["sdk"] == "anthropic":
            return anthropic.AsyncAnthropic(**model["client_params"])
        return openai.AsyncOpenAI(**model["client_params"])

    async def _chat_openai(self, messages: List[Dict]) -> str:
        """调用 OpenAI 兼容接口。"""
        try:
            response = await self.client.chat.completions.create(
                messages=messages,
                **self.model["request_params"],
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

    async def _stream_openai(
        self,
        messages: List[Dict[str, str]],
    ) -> AsyncIterator[str]:
        """流式调用 OpenAI Chat Completions 兼容接口。"""
        try:
            response = await self.client.chat.completions.create(
                messages=messages,
                stream=True,
                **self.model["request_params"],
            )
            async for chunk in response:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content
                if content:
                    yield content
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

    async def _chat_openai_responses(self, messages: List[Dict]) -> str:
        """调用 OpenAI Responses 兼容接口。"""
        try:
            response = await self.client.responses.create(
                input=messages,
                **self.model["request_params"],
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

    async def _stream_openai_responses(
        self,
        messages: List[Dict[str, str]],
    ) -> AsyncIterator[str]:
        """流式调用 OpenAI Responses 兼容接口。"""
        try:
            async with self.client.responses.stream(
                input=messages,
                **self.model["request_params"],
            ) as stream:
                async for event in stream:
                    if event.type == "response.output_text.delta":
                        content = getattr(event, "delta", "")
                        if content:
                            yield content
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
        request = dict(self.model["request_params"])
        request["messages"] = chat_messages
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

    async def _stream_anthropic(
        self,
        messages: List[Dict[str, str]],
    ) -> AsyncIterator[str]:
        """流式调用 Anthropic 兼容接口。"""
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
        request = dict(self.model["request_params"])
        request["messages"] = chat_messages
        if system_parts:
            request["system"] = "\n\n".join(system_parts)

        try:
            async with self.client.messages.stream(**request) as stream:
                async for content in stream.text_stream:
                    if content:
                        yield content
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
