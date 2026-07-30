"""按请求创建模型适配器的工厂测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.exceptions import InvalidLLMConfigurationError
from app.llm.contracts import (
    LLMGenerateRequest,
    LLMMessage,
    LLMRole,
    WebSearchPolicy,
)
from app.llm.runtime_factory import RuntimeLLMFactory


class RuntimeLLMFactoryTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.llm.client.openai.AsyncOpenAI")
    async def test_factory_uses_request_key_and_model(
        self,
        client_type,
    ) -> None:
        sdk_client = client_type.return_value
        sdk_client.responses.create = AsyncMock(
            return_value=SimpleNamespace(output_text="运行时回复")
        )

        adapter = RuntimeLLMFactory().create(
            provider="openai",
            model="gpt-5.6",
            api_key="request-secret",
        )
        result = await adapter.generate(
            LLMGenerateRequest(
                messages=(
                    LLMMessage(role=LLMRole.USER, content="你好"),
                )
            )
        )

        self.assertEqual(result.content, "运行时回复")
        self.assertEqual(result.provider, "openai")
        client_type.assert_called_once_with(
            api_key="request-secret",
            base_url="https://api.openai.com/v1",
        )

    def test_factory_rejects_empty_key(self) -> None:
        with self.assertRaisesRegex(
            InvalidLLMConfigurationError,
            "不能为空",
        ):
            RuntimeLLMFactory().create(
                provider="openai",
                model="gpt-5.6",
                api_key="",
            )

    @patch("app.llm.client.openai.AsyncOpenAI")
    async def test_required_search_rejects_unsupported_provider(
        self,
        client_type,
    ) -> None:
        adapter = RuntimeLLMFactory().create(
            provider="deepseek",
            model="deepseek-v4-flash",
            api_key="secret",
        )

        with self.assertRaisesRegex(
            InvalidLLMConfigurationError,
            "不支持",
        ):
            await adapter.generate(
                LLMGenerateRequest(
                    messages=(
                        LLMMessage(role=LLMRole.USER, content="今天的新闻"),
                    ),
                    web_search=WebSearchPolicy.REQUIRED,
                )
            )


if __name__ == "__main__":
    unittest.main()
