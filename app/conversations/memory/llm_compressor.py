import json
from typing import Dict, List, Protocol

from app.exceptions import LLMResponseError
from app.conversations.memory.compressor import (
    CompressionRequest,
    CompressionResult,
)
from app.conversations.memory.prompts.loader import (
    load_roleplay_compression_prompt,
)


class CompressionLLMClient(Protocol):
    """压缩器实际需要的最小 LLM 接口。"""

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        ...


class LLMCompressor:
    """使用 LLM 执行角色扮演历史压缩。"""

    def __init__(self, llm_client: CompressionLLMClient) -> None:
        self.llm_client = llm_client
        self.system_prompt = load_roleplay_compression_prompt()

    async def compress(
        self,
        request: CompressionRequest,
    ) -> CompressionResult:
        messages = [
            {
                "role": message["role"],
                "content": message["content"],
            }
            for message in request.messages_to_compress
        ]

        user_content = (
            f"旧摘要：\n{request.old_summary or '（无）'}\n\n"
            f"待压缩对话：\n"
            f"{json.dumps(messages, ensure_ascii=False, indent=2)}\n\n"
            f"目标：将最终摘要控制在 "
            f"{request.summary_token_budget} token 以内。"
        )

        summary = await self.llm_client.chat([
            {
                "role": "system",
                "content": self.system_prompt,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ])

        summary = summary.strip()

        if not summary:
            raise LLMResponseError("压缩器返回了空摘要")

        return CompressionResult(summary=summary)
