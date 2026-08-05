"""统一 LLM 客户端测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.llm.client import LLMClient


class LLMClientTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.llm.client.openai.AsyncOpenAI")
    async def test_configured_key_is_not_reported_as_verified(
        self,
        client_type,
    ) -> None:
        model = {
            "provider": "test",
            "sdk": "openai_chat",
            "client_params": {
                "api_key": "test-key",
                "base_url": "https://example.com/v1",
            },
            "request_params": {
                "model": "test-model",
                "max_tokens": 128,
            },
        }
        client = LLMClient(model)

        self.assertEqual(
            client.describe_active_model(),
            {
                "provider": "test",
                "model": "test-model",
                "configured": True,
                "verified": False,
            },
        )

        await client.set_connection_verified(True)
        self.assertTrue(client.describe_active_model()["verified"])

    @patch("app.llm.client.openai.AsyncOpenAI")
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

    @patch("app.llm.client.anthropic.AsyncAnthropic")
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

    @patch("app.llm.client.anthropic.AsyncAnthropic")
    async def test_anthropic_stream_yields_text_chunks(self, client_type) -> None:
        class FakeMessageStream:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

            @property
            def text_stream(self):
                async def chunks():
                    yield "第一段"
                    yield "第二段"

                return chunks()

        sdk_client = client_type.return_value
        sdk_client.messages.stream = MagicMock(
            return_value=FakeMessageStream()
        )
        model = {
            "provider": "minimax",
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

        chunks = [
            chunk
            async for chunk in LLMClient(model).stream_chat([
                {"role": "system", "content": "角色设定"},
                {"role": "user", "content": "你好"},
            ])
        ]

        self.assertEqual(chunks, ["第一段", "第二段"])
        sdk_client.messages.stream.assert_called_once_with(
            model="MiniMax-M3",
            max_tokens=8192,
            system="角色设定",
            messages=[{"role": "user", "content": "你好"}],
        )

    @patch("app.llm.client.openai.AsyncOpenAI")
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
