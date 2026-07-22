"""LLM 连接测试服务。"""

from collections.abc import Callable
from typing import Protocol

from app.llm import LLMModel
from app.services.llm_client import LLMClient


class ConnectionTestClient(Protocol):
    async def chat(self, messages: list[dict]) -> str:
        """发送连接测试消息。"""


class LLMConnectionService:
    """验证模型连接及最小指令遵循能力。"""

    def __init__(
        self,
        client_factory: Callable[[LLMModel], ConnectionTestClient] = LLMClient,
    ) -> None:
        self.client_factory = client_factory

    async def test_connection(self, model: LLMModel) -> bool:
        client = self.client_factory(model)
        reply = await client.chat([
            {
                "role": "system",
                "content": (
                    "你是连接测试器。只能回复“连接成功”四个字，"
                    "不得输出标点、解释或其他内容。"
                ),
            },
            {"role": "user", "content": "请确认连接状态。"},
        ])
        return reply.strip() == "连接成功"
