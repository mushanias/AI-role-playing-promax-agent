"""学习 Agent 正式问答的无状态 HTTP 入口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.core.dependencies import get_learning_turn_orchestrator
from app.learning.application.turn_orchestrator import (
    LearningTurnOrchestrator,
)
from app.learning.contracts.commands import ConversationCommand
from app.learning.contracts.delta import ConversationDelta


router = APIRouter(prefix="/learning", tags=["learning"])


@router.post(
    "/conversations/turns",
    response_model=ConversationDelta,
)
async def execute_learning_turn(
    command: ConversationCommand,
    api_key: Annotated[
        str,
        Header(
            alias="X-Provider-API-Key",
            min_length=1,
            include_in_schema=True,
        ),
    ],
    orchestrator: LearningTurnOrchestrator = Depends(
        get_learning_turn_orchestrator
    ),
) -> ConversationDelta:
    """使用请求级 API Key 执行问答，后端不保存命令内容。"""
    return await orchestrator.execute(command, api_key)
