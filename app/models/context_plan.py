"""分支 Context 的语义计划与候选结果。"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from app.models.conversation import SummaryVersion, Turn


@dataclass(frozen=True)
class ContextPlan:
    """一次 LLM 请求应使用的摘要、完整原文和当前输入。"""

    conversation_id: str
    branch_id: str
    summary: Optional[SummaryVersion]
    raw_turns: Tuple[Turn, ...]
    pending_turn: Optional[Turn]


@dataclass(frozen=True)
class ContextCandidate:
    """完成消息组装和 Token 估算后的 Context 候选。"""

    plan: ContextPlan
    messages: Tuple[Dict[str, str], ...]
    estimated_tokens: int
    high_watermark: int
    low_watermark: int
    recent_raw_token_target: int
    needs_compression: bool


@dataclass(frozen=True)
class ManagedContext:
    """ContextManager 最终交给聊天编排层的结果。"""

    candidate: ContextCandidate
    warnings: Tuple[str, ...]
    compression_passes: int
    degraded_messages: Optional[Tuple[Dict[str, str], ...]] = None
    degraded_estimated_tokens: Optional[int] = None

    @property
    def messages(self) -> Tuple[Dict[str, str], ...]:
        """返回可直接发送给主对话 LLM 的 messages。"""
        if self.degraded_messages is not None:
            return self.degraded_messages
        return self.candidate.messages

    @property
    def estimated_tokens(self) -> int:
        """返回实际发送载荷的 Token 估算。"""
        if self.degraded_estimated_tokens is not None:
            return self.degraded_estimated_tokens
        return self.candidate.estimated_tokens

    @property
    def quality_degraded(self) -> bool:
        """表示结果仍超过质量高水位或执行期间产生了警告。"""
        return (
            self.degraded_messages is not None
            or self.candidate.needs_compression
            or bool(self.warnings)
        )
