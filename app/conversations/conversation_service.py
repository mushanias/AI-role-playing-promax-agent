"""为 HTTP 层组合会话创建、历史读取、重写和分支切换。"""

import asyncio
from collections.abc import AsyncIterator
from typing import List, Optional, Protocol
from uuid import uuid4

from app.exceptions import BranchNotFoundError
from app.conversations.chat_turn import ChatTurnResult
from app.conversations.chat_stream import ChatStreamEvent
from app.conversations.conversation import (
    Branch,
    Conversation,
    Turn,
    TurnStatus,
)
from app.conversations.conversation_view import (
    ConversationHistory,
    ConversationSummary,
    DeletedConversationSummary,
    HistoryTurn,
)
from app.conversations.branch_service import BranchService, TurnVariant
from app.conversations.conversation_repository import ConversationRepository


class ConversationChatSender(Protocol):
    """会话应用服务依赖的最小聊天发送接口。"""

    async def send(
        self,
        conversation_id: str,
        user_input: str,
        branch_id: Optional[str] = None,
    ) -> ChatTurnResult:
        ...

    def stream(
        self,
        conversation_id: str,
        user_input: str,
        generation_id: str,
        stop_event: asyncio.Event,
        branch_id: Optional[str] = None,
    ) -> AsyncIterator[ChatStreamEvent]:
        ...


class ConversationService:
    """向路由层提供完整、与存储细节无关的会话用例。"""

    def __init__(
        self,
        repository: ConversationRepository,
        branch_service: BranchService,
        chat_service: ConversationChatSender,
    ) -> None:
        self.repository = repository
        self.branch_service = branch_service
        self.chat_service = chat_service

    async def create_conversation(self) -> Conversation:
        """创建使用服务端 UUID 的空会话。"""
        return await self.branch_service.create_conversation(str(uuid4()))

    async def list_conversations(self) -> List[ConversationSummary]:
        """返回按最近活动时间排序的侧边栏会话列表。"""
        conversations = await self.repository.list_all()
        summaries = [
            self._build_conversation_summary(conversation)
            for conversation in conversations
        ]
        summaries.sort(
            key=lambda summary: summary.updated_at,
            reverse=True,
        )
        return summaries

    async def delete_conversation(self, conversation_id: str) -> None:
        """把完整会话及其分支、Turn 和摘要移入回收站。"""
        await self.repository.delete(conversation_id)

    async def list_deleted_conversations(
        self,
    ) -> List[DeletedConversationSummary]:
        """返回按删除时间倒序排列的回收站会话。"""
        snapshots = await self.repository.list_deleted()
        summaries = [
            DeletedConversationSummary(
                conversation_id=snapshot.conversation.conversation_id,
                title=self._build_conversation_summary(
                    snapshot.conversation
                ).title,
                deleted_at=snapshot.deleted_at,
            )
            for snapshot in snapshots
        ]
        summaries.sort(
            key=lambda summary: summary.deleted_at,
            reverse=True,
        )
        return summaries

    async def restore_conversation(self, conversation_id: str) -> None:
        """从回收站恢复完整会话。"""
        await self.repository.restore(conversation_id)

    async def get_history(
        self,
        conversation_id: str,
        branch_id: Optional[str] = None,
    ) -> ConversationHistory:
        """返回指定分支的完整原文链，不用摘要替换界面消息。"""
        conversation = await self.repository.load(conversation_id)
        selected_branch_id = branch_id or conversation.active_branch_id
        branch = conversation.branches.get(selected_branch_id)
        if branch is None:
            raise BranchNotFoundError(
                f"会话分支不存在：{selected_branch_id}"
            )

        completed_turns = self._collect_completed_path(
            conversation,
            branch,
        )
        failed_turns = self._collect_failed_turns(
            conversation,
            branch,
            completed_turns,
        )
        history_turns = [
            self._build_history_turn(conversation, turn)
            for turn in [*completed_turns, *failed_turns]
        ]

        if branch.pending_turn_id is not None:
            pending_turn = conversation.turns[branch.pending_turn_id]
            history_turns.append(
                HistoryTurn(
                    turn_id=pending_turn.turn_id,
                    parent_turn_id=pending_turn.parent_turn_id,
                    user_content=pending_turn.user_content,
                    assistant_content=None,
                    status=pending_turn.status,
                    created_at=pending_turn.created_at,
                    completed_at=None,
                    response_duration_ms=None,
                    failure_message=None,
                    finish_reason=None,
                    variant_index=0,
                    variant_count=1,
                )
            )

        history_turns.sort(
            key=lambda turn: (turn.created_at, turn.turn_id)
        )

        return ConversationHistory(
            conversation_id=conversation.conversation_id,
            branch_id=selected_branch_id,
            active_branch_id=conversation.active_branch_id,
            turns=tuple(history_turns),
        )

    async def send_message(
        self,
        conversation_id: str,
        user_input: str,
        branch_id: Optional[str] = None,
    ) -> ChatTurnResult:
        """向活动分支或显式目标分支发送新消息。"""
        return await self.chat_service.send(
            conversation_id=conversation_id,
            user_input=user_input,
            branch_id=branch_id,
        )

    async def stream_message(
        self,
        conversation_id: str,
        user_input: str,
        generation_id: str,
        stop_event: asyncio.Event,
        branch_id: Optional[str] = None,
    ) -> AsyncIterator[ChatStreamEvent]:
        """逐段返回指定分支上的新回答。"""
        async for event in self.chat_service.stream(
            conversation_id=conversation_id,
            user_input=user_input,
            generation_id=generation_id,
            stop_event=stop_event,
            branch_id=branch_id,
        ):
            yield event

    async def rewrite_turn(
        self,
        conversation_id: str,
        target_turn_id: str,
        user_input: str,
        source_branch_id: Optional[str] = None,
    ) -> ChatTurnResult:
        """从目标 Turn 之前创建分支，并发送修改后的用户输入。"""
        if source_branch_id is None:
            conversation = await self.repository.load(conversation_id)
            source_branch_id = conversation.active_branch_id

        new_branch = await self.branch_service.create_branch_for_rewrite(
            conversation_id=conversation_id,
            source_branch_id=source_branch_id,
            target_turn_id=target_turn_id,
        )
        try:
            return await self.chat_service.send(
                conversation_id=conversation_id,
                user_input=user_input,
                branch_id=new_branch.branch_id,
            )
        except (Exception, asyncio.CancelledError):
            await self.branch_service.switch_branch(
                conversation_id=conversation_id,
                branch_id=source_branch_id,
            )
            raise

    async def stream_rewrite_turn(
        self,
        conversation_id: str,
        target_turn_id: str,
        user_input: str,
        generation_id: str,
        stop_event: asyncio.Event,
        source_branch_id: Optional[str] = None,
    ) -> AsyncIterator[ChatStreamEvent]:
        """创建重写分支，并逐段返回修改后的回答。"""
        if source_branch_id is None:
            conversation = await self.repository.load(conversation_id)
            source_branch_id = conversation.active_branch_id

        new_branch = await self.branch_service.create_branch_for_rewrite(
            conversation_id=conversation_id,
            source_branch_id=source_branch_id,
            target_turn_id=target_turn_id,
        )
        try:
            async for event in self.chat_service.stream(
                conversation_id=conversation_id,
                user_input=user_input,
                generation_id=generation_id,
                stop_event=stop_event,
                branch_id=new_branch.branch_id,
            ):
                yield event
        except (Exception, asyncio.CancelledError):
            await self.branch_service.switch_branch(
                conversation_id=conversation_id,
                branch_id=source_branch_id,
            )
            raise

    async def list_turn_variants(
        self,
        conversation_id: str,
        turn_id: str,
    ) -> List[TurnVariant]:
        """返回界面左右箭头对应的全部完成版本。"""
        return await self.branch_service.list_turn_variants(
            conversation_id=conversation_id,
            target_turn_id=turn_id,
        )

    async def activate_branch(
        self,
        conversation_id: str,
        branch_id: str,
    ) -> Branch:
        """切换界面当前展示与后续发送使用的会话分支。"""
        return await self.branch_service.switch_branch(
            conversation_id=conversation_id,
            branch_id=branch_id,
        )

    @staticmethod
    def _collect_completed_path(
        conversation: Conversation,
        branch: Branch,
    ) -> List[Turn]:
        reversed_turns = []
        current_turn_id = branch.head_turn_id

        while current_turn_id is not None:
            turn = conversation.turns[current_turn_id]
            reversed_turns.append(turn)
            current_turn_id = turn.parent_turn_id

        reversed_turns.reverse()
        return reversed_turns

    @staticmethod
    def _build_history_turn(
        conversation: Conversation,
        turn: Turn,
    ) -> HistoryTurn:
        variants = [
            candidate
            for candidate in conversation.turns.values()
            if candidate.parent_turn_id == turn.parent_turn_id
            and candidate.status == TurnStatus.COMPLETED
        ]
        variants.sort(
            key=lambda candidate: (
                candidate.created_at,
                candidate.turn_id,
            )
        )
        variant_ids = [candidate.turn_id for candidate in variants]
        is_completed = turn.status == TurnStatus.COMPLETED

        return HistoryTurn(
            turn_id=turn.turn_id,
            parent_turn_id=turn.parent_turn_id,
            user_content=turn.user_content,
            assistant_content=turn.assistant_content,
            status=turn.status,
            created_at=turn.created_at,
            completed_at=turn.completed_at,
            response_duration_ms=turn.response_duration_ms,
            failure_message=turn.failure_message,
            finish_reason=turn.finish_reason,
            variant_index=(
                variant_ids.index(turn.turn_id) if is_completed else 0
            ),
            variant_count=(len(variants) if is_completed else 1),
        )

    @staticmethod
    def _collect_failed_turns(
        conversation: Conversation,
        branch: Branch,
        completed_turns: List[Turn],
    ) -> List[Turn]:
        """读取分支失败尝试，并兼容升级前没有 failed_turn_ids 的单分支数据。"""
        if branch.failed_turn_ids:
            return [
                conversation.turns[turn_id]
                for turn_id in branch.failed_turn_ids
            ]

        if len(conversation.branches) != 1:
            return []

        path_ids = {turn.turn_id for turn in completed_turns}
        valid_parent_ids = path_ids | {None}
        return [
            turn
            for turn in conversation.turns.values()
            if turn.status == TurnStatus.FAILED
            and turn.parent_turn_id in valid_parent_ids
        ]

    @staticmethod
    def _build_conversation_summary(
        conversation: Conversation,
    ) -> ConversationSummary:
        turns = sorted(
            conversation.turns.values(),
            key=lambda turn: (turn.created_at, turn.turn_id),
        )
        first_content = turns[0].user_content.strip() if turns else ""
        title = first_content or "新对话"
        if len(title) > 32:
            title = f"{title[:32]}…"

        activity_times = [
            branch.created_at
            for branch in conversation.branches.values()
        ]
        activity_times.extend(turn.created_at for turn in turns)
        activity_times.extend(
            turn.completed_at
            for turn in turns
            if turn.completed_at is not None
        )

        return ConversationSummary(
            conversation_id=conversation.conversation_id,
            title=title,
            updated_at=max(activity_times),
        )
