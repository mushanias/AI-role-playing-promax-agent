"""聊天流式生成的领域事件。"""

from dataclasses import dataclass
from typing import Literal, Optional, Tuple


ChatStreamEventType = Literal[
    "started",
    "delta",
    "completed",
    "stopped",
]


@dataclass(frozen=True)
class ChatStreamEvent:
    """从会话服务流向后台任务注册表的一条生成事件。"""

    type: ChatStreamEventType
    generation_id: str
    conversation_id: str
    branch_id: str
    turn_id: str
    content: Optional[str] = None
    duration_ms: Optional[int] = None
    warnings: Tuple[str, ...] = ()
    compression_passes: int = 0
    quality_degraded: bool = False
