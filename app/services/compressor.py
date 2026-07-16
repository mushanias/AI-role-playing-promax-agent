from dataclasses import dataclass
from typing import Dict, List, Protocol


@dataclass
class CompressionRequest:
    """一次历史压缩的输入。"""

    old_summary: str
    messages_to_compress: List[Dict[str, str]]
    summary_token_budget: int


@dataclass
class CompressionResult:
    """一次历史压缩的输出。"""

    summary: str


class Compressor(Protocol):
    """可替换的历史压缩器接口。"""

    async def compress(
        self,
        request: CompressionRequest,
    ) -> CompressionResult:
        ...