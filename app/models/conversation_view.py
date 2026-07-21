"""前端读取原始剧情历史所需的只读视图模型。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from app.models.conversation import TurnStatus


@dataclass(frozen=True)
class HistoryTurn:
    """当前剧情链上的一个原始 Turn。"""

    turn_id: str
    parent_turn_id: Optional[str]
    user_content: str
    assistant_content: Optional[str]
    status: TurnStatus
    created_at: datetime
    completed_at: Optional[datetime]
    variant_index: int
    variant_count: int


@dataclass(frozen=True)
class ConversationHistory:
    """一个指定分支供界面展示的完整原文历史。"""

    conversation_id: str
    branch_id: str
    active_branch_id: str
    turns: Tuple[HistoryTurn, ...]
