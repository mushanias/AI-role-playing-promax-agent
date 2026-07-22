"""LLM 连接测试服务测试。"""

import unittest

from app.llm import build_llm_model
from app.services.llm_connection_service import LLMConnectionService


class FakeConnectionClient:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.messages = None

    async def chat(self, messages: list[dict]) -> str:
        self.messages = messages
        return self.reply


class LLMConnectionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_reply_passes_connection_test(self) -> None:
        client = FakeConnectionClient("连接成功")
        service = LLMConnectionService(lambda model: client)
        model = build_llm_model("secret", "minimax", "MiniMax-M3")

        success = await service.test_connection(model)

        self.assertTrue(success)
        self.assertEqual(client.messages[-1]["role"], "user")

    async def test_extra_content_fails_connection_test(self) -> None:
        client = FakeConnectionClient("连接成功！")
        service = LLMConnectionService(lambda model: client)
        model = build_llm_model("secret", "minimax", "MiniMax-M3")

        success = await service.test_connection(model)

        self.assertFalse(success)


if __name__ == "__main__":
    unittest.main()
