"""按请求创建模型适配器的工厂测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.exceptions import (
    InvalidLLMConfigurationError,
    LLMResponseError,
)
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

    @patch("app.llm.client.openai.AsyncOpenAI")
    async def test_openai_search_normalizes_sources_and_usage(
        self,
        client_type,
    ) -> None:
        sdk_client = client_type.return_value
        sdk_client.responses.create = AsyncMock(
            return_value=SimpleNamespace(
                output_text="联网回答",
                output=[
                    SimpleNamespace(type="web_search_call"),
                    SimpleNamespace(
                        type="message",
                        content=[
                            SimpleNamespace(
                                annotations=[
                                    SimpleNamespace(
                                        type="url_citation",
                                        title="官方资料",
                                        url="https://example.com/official",
                                    )
                                ]
                            )
                        ],
                    ),
                ],
                usage=SimpleNamespace(
                    input_tokens=12,
                    output_tokens=8,
                ),
            )
        )
        adapter = RuntimeLLMFactory().create(
            provider="openai",
            model="gpt-5.6",
            api_key="secret",
        )

        result = await adapter.generate(
            LLMGenerateRequest(
                messages=(
                    LLMMessage(role=LLMRole.USER, content="查一下"),
                ),
                web_search=WebSearchPolicy.REQUIRED,
            )
        )

        self.assertEqual(result.content, "联网回答")
        self.assertEqual(result.sources[0].title, "官方资料")
        self.assertEqual(result.usage.input_tokens, 12)
        call = sdk_client.responses.create.await_args.kwargs
        self.assertEqual(call["tools"], [{"type": "web_search"}])
        self.assertEqual(call["input"][0]["role"], "system")

    @patch("app.llm.client.openai.AsyncOpenAI")
    async def test_xai_search_accepts_response_level_citations(
        self,
        client_type,
    ) -> None:
        sdk_client = client_type.return_value
        sdk_client.responses.create = AsyncMock(
            return_value=SimpleNamespace(
                output_text="Grok 回答",
                output=[SimpleNamespace(type="web_search_call")],
                citations=["https://x.ai/news"],
                usage=None,
            )
        )
        adapter = RuntimeLLMFactory().create(
            provider="xai",
            model="grok-4.5",
            api_key="secret",
        )

        result = await adapter.generate(
            LLMGenerateRequest(
                messages=(
                    LLMMessage(role=LLMRole.USER, content="查一下"),
                ),
                web_search=WebSearchPolicy.AUTO,
            )
        )

        self.assertEqual(result.sources[0].url, "https://x.ai/news")

    @patch("app.llm.client.anthropic.AsyncAnthropic")
    async def test_anthropic_search_normalizes_citations(
        self,
        client_type,
    ) -> None:
        sdk_client = client_type.return_value
        sdk_client.messages.create = AsyncMock(
            return_value=SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="server_tool_use",
                        name="web_search",
                    ),
                    SimpleNamespace(
                        type="text",
                        text="Claude 回答",
                        citations=[
                            SimpleNamespace(
                                type="web_search_result_location",
                                title="Anthropic 文档",
                                url="https://docs.anthropic.com/search",
                            )
                        ],
                    ),
                ],
                usage=SimpleNamespace(
                    input_tokens=20,
                    output_tokens=10,
                ),
            )
        )
        adapter = RuntimeLLMFactory().create(
            provider="anthropic",
            model="claude-sonnet-5",
            api_key="secret",
        )

        result = await adapter.generate(
            LLMGenerateRequest(
                messages=(
                    LLMMessage(role=LLMRole.USER, content="查一下"),
                ),
                web_search=WebSearchPolicy.REQUIRED,
            )
        )

        self.assertEqual(result.content, "Claude 回答")
        self.assertEqual(
            result.sources[0].url,
            "https://docs.anthropic.com/search",
        )
        call = sdk_client.messages.create.await_args.kwargs
        self.assertEqual(call["tools"][0]["name"], "web_search")
        self.assertIn("必须先使用联网搜索", call["system"])

    @patch("app.llm.client.openai.AsyncOpenAI")
    async def test_glm_search_normalizes_search_results(
        self,
        client_type,
    ) -> None:
        sdk_client = client_type.return_value
        sdk_client.chat.completions.create = AsyncMock(
            return_value=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="GLM 回答 [ref_1]",
                            search_result=[
                                {
                                    "title": "智谱资料",
                                    "link": "https://example.cn/glm",
                                    "media": "示例站点",
                                }
                            ],
                        )
                    )
                ],
                usage=SimpleNamespace(
                    prompt_tokens=30,
                    completion_tokens=15,
                ),
            )
        )
        adapter = RuntimeLLMFactory().create(
            provider="glm",
            model="glm-5.2",
            api_key="secret",
        )

        result = await adapter.generate(
            LLMGenerateRequest(
                messages=(
                    LLMMessage(role=LLMRole.USER, content="查一下"),
                ),
                web_search=WebSearchPolicy.REQUIRED,
            )
        )

        self.assertEqual(result.sources[0].title, "智谱资料")
        self.assertEqual(result.sources[0].publisher, "示例站点")
        self.assertEqual(result.usage.output_tokens, 15)
        call = sdk_client.chat.completions.create.await_args.kwargs
        self.assertEqual(call["tools"][0]["type"], "web_search")

    @patch("app.llm.client.openai.AsyncOpenAI")
    async def test_required_search_fails_when_provider_did_not_search(
        self,
        client_type,
    ) -> None:
        sdk_client = client_type.return_value
        sdk_client.responses.create = AsyncMock(
            return_value=SimpleNamespace(
                output_text="未搜索的回答",
                output=[SimpleNamespace(type="message", content=[])],
                usage=None,
            )
        )
        adapter = RuntimeLLMFactory().create(
            provider="openai",
            model="gpt-5.6",
            api_key="secret",
        )

        with self.assertRaisesRegex(LLMResponseError, "没有执行搜索"):
            await adapter.generate(
                LLMGenerateRequest(
                    messages=(
                        LLMMessage(role=LLMRole.USER, content="必须查一下"),
                    ),
                    web_search=WebSearchPolicy.REQUIRED,
                )
            )


if __name__ == "__main__":
    unittest.main()
