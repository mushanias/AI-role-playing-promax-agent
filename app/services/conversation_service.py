"""为 HTTP 层组合会话创建、历史读取、重写和分支切换。"""

from typing import List, Optional, Protocol
from uuid import uuid4

from app.exceptions import BranchNotFoundError
from app.models.chat_turn import ChatTurnResult
from app.models.conversation import (
    Branch,
    Conversation,
    Turn,
    TurnStatus,
)
from app.models.conversation_view import (
    ConversationHistory,
    HistoryTurn,
)
from app.services.branch_service import BranchService, TurnVariant
from app.storage.conversation_repository import ConversationRepository


class ConversationChatSender(Protocol):
    """会话应用服务依赖的最小聊天发送接口。"""

    async def send(
        self,
        conversation_id: str,
        user_input: str,
        branch_id: Optional[str] = None,
    ) -> ChatTurnResult:
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
                f"剧情分支不存在：{selected_branch_id}"
            )

        completed_turns = self._collect_completed_path(
            conversation,
            branch,
        )
        history_turns = [
            self._build_history_turn(conversation, turn)
            for turn in completed_turns
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
                    variant_index=0,
                    variant_count=1,
                )
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
        return await self.chat_service.send(
            conversation_id=conversation_id,
            user_input=user_input,
            branch_id=new_branch.branch_id,
        )

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
        """切换界面当前展示与后续发送使用的剧情分支。"""
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

        return HistoryTurn(
            turn_id=turn.turn_id,
            parent_turn_id=turn.parent_turn_id,
            user_content=turn.user_content,
            assistant_content=turn.assistant_content,
            status=turn.status,
            created_at=turn.created_at,
            completed_at=turn.completed_at,
            variant_index=variant_ids.index(turn.turn_id),
            variant_count=len(variants),
        )
