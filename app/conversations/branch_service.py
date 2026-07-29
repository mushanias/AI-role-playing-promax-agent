"""会话分支服务：创建、切换分支并查询同位置消息版本。"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from app.exceptions import (
    BranchNotFoundError,
    InvalidBranchOperationError,
    TurnNotFoundError,
)
from app.conversations.conversation import (
    Branch,
    Conversation,
    SummaryVersion,
    Turn,
    TurnStatus,
)
from app.conversations.conversation_repository import ConversationRepository


@dataclass(frozen=True)
class TurnVariant:
    """前端消息版本箭头所需的单个版本信息。"""

    turn_id: str
    branch_id: str
    user_content: str
    created_at: datetime
    is_active: bool


class BranchService:
    """处理会话分支创建、旧消息重写和版本切换。"""

    def __init__(self, repository: ConversationRepository) -> None:
        self.repository = repository

    async def create_conversation(
        self,
        conversation_id: str,
    ) -> Conversation:
        """创建带一个空根分支的新会话。"""
        now = datetime.now(timezone.utc)
        root_branch = Branch(
            branch_id=str(uuid4()),
            created_at=now,
        )
        conversation = Conversation(
            conversation_id=conversation_id,
            active_branch_id=root_branch.branch_id,
            branches={root_branch.branch_id: root_branch},
        )

        await self.repository.create(conversation)
        return conversation

    async def create_branch_for_rewrite(
        self,
        conversation_id: str,
        source_branch_id: str,
        target_turn_id: str,
    ) -> Branch:
        """从目标 Turn 之前创建一条新的活动会话分支。"""
        new_branch_id = str(uuid4())
        created_at = datetime.now(timezone.utc)

        def create_branch(conversation: Conversation) -> Conversation:
            source_branch = self._get_branch(
                conversation,
                source_branch_id,
            )
            if source_branch.pending_turn_id is not None:
                raise InvalidBranchOperationError(
                    "来源分支仍有正在生成的轮次，暂时不能创建新分支"
                )

            target_turn = self._get_turn(conversation, target_turn_id)
            if target_turn.status != TurnStatus.COMPLETED:
                raise InvalidBranchOperationError(
                    "只能修改已经完成的用户消息"
                )
            if source_branch.head_turn_id is None or not self._is_turn_ancestor(
                conversation,
                ancestor_turn_id=target_turn_id,
                descendant_turn_id=source_branch.head_turn_id,
            ):
                raise InvalidBranchOperationError(
                    "目标轮次不在来源分支的当前历史链上"
                )

            retained_head_id = target_turn.parent_turn_id
            active_summary_id = self._resolve_unrolled_summary_id(
                conversation=conversation,
                source_branch=source_branch,
                retained_head_id=retained_head_id,
            )
            new_branch = Branch(
                branch_id=new_branch_id,
                parent_branch_id=source_branch_id,
                forked_from_turn_id=retained_head_id,
                head_turn_id=retained_head_id,
                active_summary_id=active_summary_id,
                created_at=created_at,
            )

            conversation.branches[new_branch_id] = new_branch
            conversation.active_branch_id = new_branch_id
            return conversation

        updated = await self.repository.update(
            conversation_id,
            create_branch,
        )
        return updated.branches[new_branch_id]

    async def list_turn_variants(
        self,
        conversation_id: str,
        target_turn_id: str,
    ) -> List[TurnVariant]:
        """列出与目标 Turn 位于同一对话位置的已完成版本。"""
        conversation = await self.repository.load(conversation_id)
        target_turn = self._get_turn(conversation, target_turn_id)
        if target_turn.status != TurnStatus.COMPLETED:
            raise InvalidBranchOperationError(
                "只有已完成轮次才存在可切换的消息版本"
            )

        siblings = [
            turn
            for turn in conversation.turns.values()
            if turn.parent_turn_id == target_turn.parent_turn_id
            and turn.status == TurnStatus.COMPLETED
        ]
        siblings.sort(key=lambda turn: (turn.created_at, turn.turn_id))

        active_branch = conversation.branches[
            conversation.active_branch_id
        ]
        variants: List[TurnVariant] = []

        for sibling in siblings:
            is_active = self._branch_contains_turn(
                conversation,
                active_branch,
                sibling.turn_id,
            )
            representative = self._find_representative_branch(
                conversation,
                sibling.turn_id,
                prefer_branch_id=(
                    active_branch.branch_id if is_active else None
                ),
            )
            variants.append(
                TurnVariant(
                    turn_id=sibling.turn_id,
                    branch_id=representative.branch_id,
                    user_content=sibling.user_content,
                    created_at=sibling.created_at,
                    is_active=is_active,
                )
            )

        return variants

    async def switch_branch(
        self,
        conversation_id: str,
        branch_id: str,
    ) -> Branch:
        """切换当前界面使用的会话分支。"""
        def switch(conversation: Conversation) -> Conversation:
            self._get_branch(conversation, branch_id)
            conversation.active_branch_id = branch_id
            return conversation

        updated = await self.repository.update(conversation_id, switch)
        return updated.branches[branch_id]

    @staticmethod
    def _get_branch(
        conversation: Conversation,
        branch_id: str,
    ) -> Branch:
        branch = conversation.branches.get(branch_id)
        if branch is None:
            raise BranchNotFoundError(f"会话分支不存在：{branch_id}")
        return branch

    @staticmethod
    def _get_turn(
        conversation: Conversation,
        turn_id: str,
    ) -> Turn:
        turn = conversation.turns.get(turn_id)
        if turn is None:
            raise TurnNotFoundError(f"原始轮次不存在：{turn_id}")
        return turn

    def _resolve_unrolled_summary_id(
        self,
        conversation: Conversation,
        source_branch: Branch,
        retained_head_id: Optional[str],
    ) -> Optional[str]:
        """找到回退点可用的最近摘要，再把指针向父摘要移动一层。"""
        if retained_head_id is None:
            return None

        summary_id = source_branch.active_summary_id
        while summary_id is not None:
            summary = conversation.summaries[summary_id]
            if self._is_turn_ancestor(
                conversation,
                ancestor_turn_id=summary.covered_until_turn_id,
                descendant_turn_id=retained_head_id,
            ):
                return summary.parent_summary_id
            summary_id = summary.parent_summary_id

        return None

    def _find_representative_branch(
        self,
        conversation: Conversation,
        turn_id: str,
        prefer_branch_id: Optional[str],
    ) -> Branch:
        if prefer_branch_id is not None:
            preferred = conversation.branches[prefer_branch_id]
            if self._branch_contains_turn(
                conversation,
                preferred,
                turn_id,
            ):
                return preferred

        candidates = [
            branch
            for branch in conversation.branches.values()
            if self._branch_contains_turn(conversation, branch, turn_id)
        ]
        if not candidates:
            raise InvalidBranchOperationError(
                f"轮次 {turn_id} 没有可切换的会话分支"
            )

        return min(
            candidates,
            key=lambda branch: (branch.created_at, branch.branch_id),
        )

    def _branch_contains_turn(
        self,
        conversation: Conversation,
        branch: Branch,
        turn_id: str,
    ) -> bool:
        if branch.head_turn_id is None:
            return False
        return self._is_turn_ancestor(
            conversation,
            ancestor_turn_id=turn_id,
            descendant_turn_id=branch.head_turn_id,
        )

    @staticmethod
    def _is_turn_ancestor(
        conversation: Conversation,
        ancestor_turn_id: str,
        descendant_turn_id: str,
    ) -> bool:
        current_turn_id: Optional[str] = descendant_turn_id

        while current_turn_id is not None:
            if current_turn_id == ancestor_turn_id:
                return True
            current_turn_id = conversation.turns[
                current_turn_id
            ].parent_turn_id

        return False
