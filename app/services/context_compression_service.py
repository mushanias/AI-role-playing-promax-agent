from dataclasses import dataclass
from typing import Dict, List

from app.models.context_state import ContextState
from app.services.compression_batch_selector import (
    CompressionBatchSelector,
)
from app.services.compressor import (
    CompressionRequest,
    Compressor,
)


@dataclass
class CompressionAttempt:
    """一次压缩尝试的结果。"""

    next_state: ContextState
    compressed: bool


class ContextCompressionService:
    """编排压缩批次选择、LLM 压缩和状态更新。"""

    def __init__(
        self,
        batch_selector: CompressionBatchSelector,
        compressor: Compressor,
        summary_token_budget: int,
    ) -> None:
        if summary_token_budget <= 0:
            raise ValueError("摘要 token 预算必须大于 0")

        self.batch_selector = batch_selector
        self.compressor = compressor
        self.summary_token_budget = summary_token_budget

    async def compress(
        self,
        state: ContextState,
        recent_messages: List[Dict[str, str]],
    ) -> CompressionAttempt:
        batch = self.batch_selector.select(recent_messages)

        if not batch:
            return CompressionAttempt(
                next_state=state,
                compressed=False,
            )

        result = await self.compressor.compress(
            CompressionRequest(
                old_summary=state.summary,
                messages_to_compress=batch,
                summary_token_budget=self.summary_token_budget,
            )
        )

        next_state = ContextState(
            summary=result.summary,
            compressed_until_message_id=batch[-1]["message_id"],
        )

        return CompressionAttempt(
            next_state=next_state,
            compressed=True,
        )