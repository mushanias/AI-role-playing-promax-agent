"""追加式摘要压缩的计划与执行结果。"""

from dataclasses import dataclass
from typing import Optional, Tuple

from app.conversations.conversation import SummaryVersion, Turn
from app.conversations.memory.context_plan import ContextCandidate


@dataclass(frozen=True)
class VersionedCompressionPlan:
    """一次同步压缩所需的稳定输入与并发校验指针。"""

    conversation_id: str
    branch_id: str
    expected_head_turn_id: Optional[str]
    expected_pending_turn_id: Optional[str]
    expected_active_summary_id: Optional[str]
    old_summary: str
    turns_to_compress: Tuple[Turn, ...]
    raw_turns_to_keep: Tuple[Turn, ...]
    summary_token_budget: int
    estimated_result_upper_bound: int


@dataclass(frozen=True)
class VersionedCompressionOutcome:
    """同步压缩后的候选 Context、摘要和降级状态。"""

    candidate: ContextCandidate
    summary: Optional[SummaryVersion]
    compressed: bool
    stale: bool
    warning: Optional[str]
