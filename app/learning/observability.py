"""学习操作的结构化可观测事件。"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class LearningStage(str, Enum):
    """一次问答编排中的稳定阶段名称。"""

    VALIDATION = "validation"
    RETRIEVAL = "retrieval"
    CONTEXT = "context"
    MODEL = "model"
    COMPLETE = "complete"


@dataclass(frozen=True)
class LearningOperationEvent:
    """不包含秘密和正文的单阶段执行指标。"""

    operation_id: str
    goal_id: str
    conversation_id: str
    turn_id: str
    provider: str
    model: str
    stage: LearningStage
    elapsed_seconds: float
    retrieval_hits: int = 0
    warning_count: int = 0


class LearningOperationObserver(Protocol):
    """应用编排层依赖的观测出口。"""

    def record(self, event: LearningOperationEvent) -> None:
        """记录一条不影响主流程的阶段事件。"""


class LoggingLearningObserver:
    """把学习操作指标写入现有结构化日志。"""

    def __init__(self) -> None:
        self.logger = logging.getLogger("learning.operation")

    def record(self, event: LearningOperationEvent) -> None:
        self.logger.info(
            "学习操作：operation=%s goal=%s conversation=%s turn=%s "
            "provider=%s model=%s stage=%s elapsed=%.3fs hits=%s warnings=%s",
            event.operation_id,
            event.goal_id,
            event.conversation_id,
            event.turn_id,
            event.provider,
            event.model,
            event.stage.value,
            event.elapsed_seconds,
            event.retrieval_hits,
            event.warning_count,
        )
