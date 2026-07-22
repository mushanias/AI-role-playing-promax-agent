"""统一 LLM 客户端测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.llm_client import LLMClient


class LLMClientTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.services.llm_client.openai.AsyncOpenAI")
    async def test_openai_sdk_keeps_original_message_format(self, client_type) -> None:
        sdk_client = client_type.return_value
        sdk_client.chat.completions.create = AsyncMock(
            return_value=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="OpenAI 回复")
                    )
                ]
            )
        )
        model = {
            "sdk": "openai_chat",
            "client_params": {
                "api_key": "test-key",
                "base_url": "https://example.com/v1",
            },
            "request_params": {
                "model": "test-model",
                "max_tokens": 4096,
            },
        }
        messages = [
            {"role": "system", "content": "系统设定"},
            {"role": "user", "content": "你好"},
        ]

        reply = await LLMClient(model).chat(messages)

        self.assertEqual(reply, "OpenAI 回复")
        sdk_client.chat.completions.create.assert_awaited_once_with(
            model="test-model",
            max_tokens=4096,
            messages=messages,
        )

    @patch("app.services.llm_client.anthropic.AsyncAnthropic")
    async def test_anthropic_sdk_separates_system_and_text_reply(self, client_type) -> None:
        sdk_client = client_type.return_value
        sdk_client.messages.create = AsyncMock(
            return_value=SimpleNamespace(
                content=[
                    SimpleNamespace(type="thinking", thinking="思考过程"),
                    SimpleNamespace(type="text", text="MiniMax 回复"),
                ]
            )
        )
        model = {
            "sdk": "anthropic",
            "client_params": {
                "api_key": "test-key",
                "base_url": "https://api.minimaxi.com/anthropic",
            },
            "request_params": {
                "model": "MiniMax-M3",
                "max_tokens": 8192,
            },
        }

        reply = await LLMClient(model).chat([
            {"role": "system", "content": "角色设定"},
            {"role": "user", "content": "你好"},
        ])

        self.assertEqual(reply, "MiniMax 回复")
        sdk_client.messages.create.assert_awaited_once_with(
            model="MiniMax-M3",
            max_tokens=8192,
            system="角色设定",
            messages=[{"role": "user", "content": "你好"}],
        )

    @patch("app.services.llm_client.openai.AsyncOpenAI")
    async def test_openai_responses_adapter_returns_output_text(self, client_type) -> None:
        sdk_client = client_type.return_value
        sdk_client.responses.create = AsyncMock(
            return_value=SimpleNamespace(output_text="Responses 回复")
        )
        model = {
            "sdk": "openai_responses",
            "client_params": {
                "api_key": "test-key",
                "base_url": "https://api.openai.com/v1",
            },
            "request_params": {
                "model": "gpt-5.6",
                "max_output_tokens": 2048,
            },
        }
        messages = [{"role": "user", "content": "你好"}]

        reply = await LLMClient(model).chat(messages)

        self.assertEqual(reply, "Responses 回复")
        sdk_client.responses.create.assert_awaited_once_with(
            model="gpt-5.6",
            input=messages,
            max_output_tokens=2048,
        )


if __name__ == "__main__":
    unittest.main()
