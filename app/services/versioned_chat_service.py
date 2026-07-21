"""按 Turn 生命周期编排分支 Context、主 LLM 与原文持久化。"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol
from uuid import uuid4

from app.exceptions import (
    BranchNotFoundError,
    InvalidBranchOperationError,
    TurnNotFoundError,
)
from app.models.chat_turn import ChatTurnResult
from app.models.context_plan import ManagedContext
from app.models.conversation import Conversation, Turn, TurnStatus
from app.storage.conversation_repository import ConversationRepository

logger = logging.getLogger(__name__)


class ManagedContextBuilder(Protocol):
    """新版 ChatService 依赖的最小 ContextManager 接口。"""

    async def build(
        self,
        conversation_id: str,
        branch_id: Optional[str] = None,
    ) -> ManagedContext:
        ...


class ChatLLMClient(Protocol):
    """新版 ChatService 依赖的最小主对话 LLM 接口。"""

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        ...


class VersionedChatService:
    """创建 pending Turn，调用 LLM，并提交 completed/failed 状态。"""

    def __init__(
        self,
        repository: ConversationRepository,
        llm_client: ChatLLMClient,
        context_manager: ManagedContextBuilder,
    ) -> None:
        self.repository = repository
        self.llm_client = llm_client
        self.context_manager = context_manager

    async def send(
        self,
        conversation_id: str,
        user_input: str,
        branch_id: Optional[str] = None,
    ) -> ChatTurnResult:
        """在指定分支上完成一次用户输入与助手回复。"""
        turn_id = str(uuid4())
        selected_branch_id = await self._create_pending_turn(
            conversation_id=conversation_id,
            branch_id=branch_id,
            turn_id=turn_id,
            user_input=user_input,
        )

        try:
            context = await self.context_manager.build(
                conversation_id=conversation_id,
                branch_id=selected_branch_id,
            )
            reply = await self.llm_client.chat(list(context.messages))
            await self._complete_turn(
                conversation_id=conversation_id,
                branch_id=selected_branch_id,
                turn_id=turn_id,
                reply=reply,
            )
        except asyncio.CancelledError:
            await asyncio.shield(
                self._mark_turn_failed_safely(
                    conversation_id=conversation_id,
                    branch_id=selected_branch_id,
                    turn_id=turn_id,
                    failure_message="请求已取消",
                )
            )
            raise
        except Exception as error:
            await self._mark_turn_failed_safely(
                conversation_id=conversation_id,
                branch_id=selected_branch_id,
                turn_id=turn_id,
                failure_message=self._describe_failure(error),
            )
            raise

        return ChatTurnResult(
            conversation_id=conversation_id,
            branch_id=selected_branch_id,
            turn_id=turn_id,
            reply=reply,
            warnings=context.warnings,
            compression_passes=context.compression_passes,
            quality_degraded=context.quality_degraded,
        )

    async def _create_pending_turn(
        self,
        conversation_id: str,
        branch_id: Optional[str],
        turn_id: str,
        user_input: str,
    ) -> str:
        created_at = datetime.now(timezone.utc)

        def create(conversation: Conversation) -> Conversation:
            selected_branch_id = (
                branch_id or conversation.active_branch_id
            )
            branch = conversation.branches.get(selected_branch_id)
            if branch is None:
                raise BranchNotFoundError(
                    f"剧情分支不存在：{selected_branch_id}"
                )
            if branch.pending_turn_id is not None:
                raise InvalidBranchOperationError(
                    "当前剧情分支已有正在生成的轮次"
                )

            pending_turn = Turn(
                turn_id=turn_id,
                parent_turn_id=branch.head_turn_id,
                user_content=user_input,
                status=TurnStatus.PENDING,
                created_at=created_at,
            )
            conversation.turns[turn_id] = pending_turn
            branch.pending_turn_id = turn_id
            return conversation

        updated = await self.repository.update(conversation_id, create)
        for current_branch in updated.branches.values():
            if current_branch.pending_turn_id == turn_id:
                return current_branch.branch_id

        raise InvalidBranchOperationError(
            "pending Turn 已创建，但无法定位所属剧情分支"
        )

    async def _complete_turn(
        self,
        conversation_id: str,
        branch_id: str,
        turn_id: str,
        reply: str,
    ) -> None:
        completed_at = datetime.now(timezone.utc)

        def complete(conversation: Conversation) -> Conversation:
            branch = conversation.branches.get(branch_id)
            if branch is None:
                raise BranchNotFoundError(
                    f"剧情分支不存在：{branch_id}"
                )
            turn = conversation.turns.get(turn_id)
            if turn is None:
                raise TurnNotFoundError(
                    f"原始轮次不存在：{turn_id}"
                )
            if (
                branch.pending_turn_id != turn_id
                or turn.status != TurnStatus.PENDING
            ):
                raise InvalidBranchOperationError(
                    "只能完成当前分支正在生成的轮次"
                )

            turn.assistant_content = reply
            turn.status = TurnStatus.COMPLETED
            turn.completed_at = completed_at
            branch.head_turn_id = turn_id
            branch.pending_turn_id = None
            return conversation

        await self.repository.update(conversation_id, complete)

    async def _mark_turn_failed_safely(
        self,
        conversation_id: str,
        branch_id: str,
        turn_id: str,
        failure_message: str,
    ) -> None:
        try:
            await self._mark_turn_failed(
                conversation_id=conversation_id,
                branch_id=branch_id,
                turn_id=turn_id,
                failure_message=failure_message,
            )
        except Exception:
            logger.exception(
                "无法保存 failed Turn：conversation=%s branch=%s turn=%s",
                conversation_id,
                branch_id,
                turn_id,
            )

    async def _mark_turn_failed(
        self,
        conversation_id: str,
        branch_id: str,
        turn_id: str,
        failure_message: str,
    ) -> None:
        def fail(conversation: Conversation) -> Conversation:
            branch = conversation.branches.get(branch_id)
            if branch is None:
                raise BranchNotFoundError(
                    f"剧情分支不存在：{branch_id}"
                )
            turn = conversation.turns.get(turn_id)
            if turn is None:
                raise TurnNotFoundError(
                    f"原始轮次不存在：{turn_id}"
                )
            if (
                branch.pending_turn_id != turn_id
                or turn.status != TurnStatus.PENDING
            ):
                raise InvalidBranchOperationError(
                    "只能把当前分支正在生成的轮次标记为失败"
                )

            turn.status = TurnStatus.FAILED
            turn.failure_message = failure_message
            branch.pending_turn_id = None
            return conversation

        await self.repository.update(conversation_id, fail)

    @staticmethod
    def _describe_failure(error: Exception) -> str:
        message = str(error).strip()
        if not message:
            return error.__class__.__name__
        return f"{error.__class__.__name__}: {message}"
