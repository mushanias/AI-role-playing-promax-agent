"""BranchService 测试。"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from app.exceptions import InvalidBranchOperationError
from app.models.conversation import (
    Branch,
    Conversation,
    SummaryVersion,
    Turn,
    TurnStatus,
)
from app.services.branch_service import BranchService
from app.storage.conversation_repository import ConversationRepository


NOW = datetime.now(timezone.utc)


def completed_turn(
    turn_id: str,
    parent_turn_id: str | None,
    order: int,
) -> Turn:
    """创建具有稳定时间顺序的完成轮次。"""
    created_at = NOW + timedelta(seconds=order)
    return Turn(
        turn_id=turn_id,
        parent_turn_id=parent_turn_id,
        user_content=f"用户输入 {turn_id}",
        assistant_content=f"助手回复 {turn_id}",
        status=TurnStatus.COMPLETED,
        created_at=created_at,
        completed_at=created_at,
    )


def linear_conversation() -> Conversation:
    """创建三轮主线和两层摘要。"""
    turn_1 = completed_turn("turn-1", None, 1)
    turn_2 = completed_turn("turn-2", "turn-1", 2)
    turn_3 = completed_turn("turn-3", "turn-2", 3)
    summary_a = SummaryVersion(
        summary_id="summary-a",
        covered_until_turn_id="turn-1",
        content="第一层摘要",
        created_at=NOW + timedelta(seconds=4),
    )
    summary_b = SummaryVersion(
        summary_id="summary-b",
        parent_summary_id="summary-a",
        covered_until_turn_id="turn-2",
        content="第二层摘要",
        created_at=NOW + timedelta(seconds=5),
    )
    main_branch = Branch(
        branch_id="branch-main",
        head_turn_id="turn-3",
        active_summary_id="summary-b",
        created_at=NOW,
    )
    return Conversation(
        conversation_id="conversation-1",
        active_branch_id="branch-main",
        turns={
            "turn-1": turn_1,
            "turn-2": turn_2,
            "turn-3": turn_3,
        },
        branches={"branch-main": main_branch},
        summaries={
            "summary-a": summary_a,
            "summary-b": summary_b,
        },
    )


class BranchServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = ConversationRepository(
            self.temporary_directory.name
        )
        self.service = BranchService(self.repository)

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_create_conversation_adds_empty_root_branch(self) -> None:
        conversation = await self.service.create_conversation(
            "conversation-new"
        )

        self.assertEqual(len(conversation.branches), 1)
        root = conversation.branches[conversation.active_branch_id]
        self.assertIsNone(root.parent_branch_id)
        self.assertIsNone(root.head_turn_id)

    async def test_rewrite_third_turn_moves_summary_up_one_level(self) -> None:
        await self.repository.create(linear_conversation())

        branch = await self.service.create_branch_for_rewrite(
            conversation_id="conversation-1",
            source_branch_id="branch-main",
            target_turn_id="turn-3",
        )
        loaded = await self.repository.load("conversation-1")

        self.assertEqual(branch.head_turn_id, "turn-2")
        self.assertEqual(branch.forked_from_turn_id, "turn-2")
        self.assertEqual(branch.active_summary_id, "summary-a")
        self.assertEqual(loaded.active_branch_id, branch.branch_id)
        self.assertIn("turn-3", loaded.turns)

    async def test_rewrite_before_active_summary_unrolls_again(self) -> None:
        await self.repository.create(linear_conversation())

        branch = await self.service.create_branch_for_rewrite(
            conversation_id="conversation-1",
            source_branch_id="branch-main",
            target_turn_id="turn-2",
        )

        self.assertEqual(branch.head_turn_id, "turn-1")
        self.assertIsNone(branch.active_summary_id)

    async def test_rewrite_first_turn_starts_from_empty_history(self) -> None:
        await self.repository.create(linear_conversation())

        branch = await self.service.create_branch_for_rewrite(
            conversation_id="conversation-1",
            source_branch_id="branch-main",
            target_turn_id="turn-1",
        )

        self.assertIsNone(branch.head_turn_id)
        self.assertIsNone(branch.forked_from_turn_id)
        self.assertIsNone(branch.active_summary_id)

    async def test_rewrite_rejects_turn_outside_source_branch(self) -> None:
        conversation = linear_conversation()
        other_turn = completed_turn("turn-other", "turn-1", 10)
        other_branch = Branch(
            branch_id="branch-other",
            parent_branch_id="branch-main",
            forked_from_turn_id="turn-1",
            head_turn_id="turn-other",
            created_at=NOW + timedelta(seconds=10),
        )
        conversation.turns[other_turn.turn_id] = other_turn
        conversation.branches[other_branch.branch_id] = other_branch
        conversation = Conversation.model_validate(
            conversation.model_dump(mode="python")
        )
        await self.repository.create(conversation)

        with self.assertRaises(InvalidBranchOperationError):
            await self.service.create_branch_for_rewrite(
                conversation_id="conversation-1",
                source_branch_id="branch-main",
                target_turn_id="turn-other",
            )

    async def test_variants_support_arrow_and_branch_switch(self) -> None:
        await self.repository.create(linear_conversation())
        new_branch = await self.service.create_branch_for_rewrite(
            conversation_id="conversation-1",
            source_branch_id="branch-main",
            target_turn_id="turn-3",
        )

        def finish_alternative(
            conversation: Conversation,
        ) -> Conversation:
            alternative = completed_turn("turn-3-alt", "turn-2", 20)
            conversation.turns[alternative.turn_id] = alternative
            branch = conversation.branches[new_branch.branch_id]
            branch.head_turn_id = alternative.turn_id
            return conversation

        await self.repository.update(
            "conversation-1",
            finish_alternative,
        )

        variants = await self.service.list_turn_variants(
            "conversation-1",
            "turn-3",
        )

        self.assertEqual(
            [variant.turn_id for variant in variants],
            ["turn-3", "turn-3-alt"],
        )
        self.assertEqual(len(variants), 2)
        active_variant = next(
            variant for variant in variants if variant.is_active
        )
        self.assertEqual(active_variant.turn_id, "turn-3-alt")

        original_variant = next(
            variant for variant in variants if variant.turn_id == "turn-3"
        )
        switched = await self.service.switch_branch(
            "conversation-1",
            original_variant.branch_id,
        )
        self.assertEqual(switched.branch_id, "branch-main")

        loaded = await self.repository.load("conversation-1")
        self.assertEqual(loaded.active_branch_id, "branch-main")
        self.assertIn("turn-3-alt", loaded.turns)

    async def test_single_version_does_not_require_arrow(self) -> None:
        await self.repository.create(linear_conversation())

        variants = await self.service.list_turn_variants(
            "conversation-1",
            "turn-3",
        )

        self.assertEqual(len(variants), 1)


if __name__ == "__main__":
    unittest.main()
