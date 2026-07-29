"""对话历史、重写与分支切换应用服务测试。"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from app.conversations.branch_service import BranchService
from app.conversations.chat_turn import ChatTurnResult
from app.conversations.conversation import (
    Branch,
    Conversation,
    Turn,
    TurnStatus,
)
from app.conversations.conversation_repository import ConversationRepository
from app.conversations.conversation_service import ConversationService


NOW = datetime.now(timezone.utc)


def completed_turn(
    turn_id: str,
    parent_turn_id: str | None,
    order: int,
    user_content: str,
) -> Turn:
    timestamp = NOW + timedelta(seconds=order)
    return Turn(
        turn_id=turn_id,
        parent_turn_id=parent_turn_id,
        user_content=user_content,
        assistant_content=f"回复：{user_content}",
        status=TurnStatus.COMPLETED,
        created_at=timestamp,
        completed_at=timestamp,
    )


def branched_conversation() -> Conversation:
    turn_1 = completed_turn("turn-1", None, 1, "第一轮")
    turn_2a = completed_turn("turn-2a", "turn-1", 2, "第二轮 A")
    turn_3a = completed_turn("turn-3a", "turn-2a", 3, "第三轮 A")
    turn_2b = completed_turn("turn-2b", "turn-1", 4, "第二轮 B")
    main_branch = Branch(
        branch_id="branch-main",
        head_turn_id="turn-3a",
        created_at=NOW,
    )
    other_branch = Branch(
        branch_id="branch-other",
        parent_branch_id="branch-main",
        forked_from_turn_id="turn-1",
        head_turn_id="turn-2b",
        created_at=NOW + timedelta(seconds=4),
    )
    return Conversation(
        conversation_id="conversation-1",
        active_branch_id="branch-main",
        turns={
            turn.turn_id: turn
            for turn in (turn_1, turn_2a, turn_3a, turn_2b)
        },
        branches={
            main_branch.branch_id: main_branch,
            other_branch.branch_id: other_branch,
        },
    )


class RecordingChatService:
    """记录发送目标，不实际调用 LLM。"""

    def __init__(self) -> None:
        self.calls = []

    async def send(
        self,
        conversation_id,
        user_input,
        branch_id=None,
    ):
        self.calls.append((conversation_id, user_input, branch_id))
        return ChatTurnResult(
            conversation_id=conversation_id,
            branch_id=branch_id,
            turn_id="generated-turn",
            reply="生成回复",
            warnings=("测试警告",),
            compression_passes=1,
            quality_degraded=True,
        )


class ConversationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = ConversationRepository(
            self.temporary_directory.name
        )
        await self.repository.create(branched_conversation())
        self.chat_service = RecordingChatService()
        self.service = ConversationService(
            repository=self.repository,
            branch_service=BranchService(self.repository),
            chat_service=self.chat_service,
        )

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_create_conversation_returns_empty_root_branch(self) -> None:
        created = await self.service.create_conversation()

        self.assertIn(created.active_branch_id, created.branches)
        self.assertIsNone(
            created.branches[created.active_branch_id].head_turn_id
        )
        self.assertTrue(await self.repository.exists(
            created.conversation_id
        ))

    async def test_history_returns_original_path_and_variant_metadata(self) -> None:
        history = await self.service.get_history("conversation-1")

        self.assertEqual(history.branch_id, "branch-main")
        self.assertEqual(
            [turn.turn_id for turn in history.turns],
            ["turn-1", "turn-2a", "turn-3a"],
        )
        second_turn = history.turns[1]
        self.assertEqual(second_turn.user_content, "第二轮 A")
        self.assertEqual(second_turn.variant_count, 2)
        self.assertEqual(second_turn.variant_index, 0)

    async def test_explicit_history_does_not_switch_active_branch(self) -> None:
        history = await self.service.get_history(
            "conversation-1",
            branch_id="branch-other",
        )
        loaded = await self.repository.load("conversation-1")

        self.assertEqual(
            [turn.turn_id for turn in history.turns],
            ["turn-1", "turn-2b"],
        )
        self.assertEqual(history.active_branch_id, "branch-main")
        self.assertEqual(loaded.active_branch_id, "branch-main")

    async def test_history_appends_current_pending_turn(self) -> None:
        pending_turn = Turn(
            turn_id="turn-pending",
            parent_turn_id="turn-3a",
            user_content="正在生成的第四轮",
            status=TurnStatus.PENDING,
            created_at=NOW + timedelta(seconds=5),
        )

        def add_pending(conversation: Conversation) -> Conversation:
            conversation.turns[pending_turn.turn_id] = pending_turn
            conversation.branches[
                "branch-main"
            ].pending_turn_id = pending_turn.turn_id
            return conversation

        await self.repository.update("conversation-1", add_pending)

        history = await self.service.get_history("conversation-1")

        self.assertEqual(history.turns[-1].turn_id, "turn-pending")
        self.assertEqual(history.turns[-1].status, TurnStatus.PENDING)
        self.assertIsNone(history.turns[-1].assistant_content)

    async def test_rewrite_creates_branch_before_target_turn(self) -> None:
        result = await self.service.rewrite_turn(
            conversation_id="conversation-1",
            target_turn_id="turn-3a",
            user_input="修改后的第三轮",
        )
        loaded = await self.repository.load("conversation-1")
        new_branch = loaded.branches[result.branch_id]

        self.assertEqual(new_branch.parent_branch_id, "branch-main")
        self.assertEqual(new_branch.head_turn_id, "turn-2a")
        self.assertEqual(new_branch.forked_from_turn_id, "turn-2a")
        self.assertEqual(loaded.active_branch_id, new_branch.branch_id)
        self.assertEqual(self.chat_service.calls, [
            (
                "conversation-1",
                "修改后的第三轮",
                new_branch.branch_id,
            )
        ])

    async def test_variants_and_activation_change_active_history(self) -> None:
        variants = await self.service.list_turn_variants(
            "conversation-1",
            "turn-2a",
        )
        other = next(
            variant for variant in variants
            if variant.turn_id == "turn-2b"
        )

        await self.service.activate_branch(
            "conversation-1",
            other.branch_id,
        )
        history = await self.service.get_history("conversation-1")

        self.assertEqual(history.branch_id, "branch-other")
        self.assertEqual(history.turns[-1].turn_id, "turn-2b")


if __name__ == "__main__":
    unittest.main()
