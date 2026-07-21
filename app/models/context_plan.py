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
