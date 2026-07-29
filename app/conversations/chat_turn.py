"""会话消息发送完成一轮后的稳定返回结果。"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ChatTurnResult:
    """一个 completed Turn 及其 Context 质量信息。"""

    conversation_id: str
    branch_id: str
    turn_id: str
    reply: str
    warnings: Tuple[str, ...]
    compression_passes: int
    quality_degraded: bool
