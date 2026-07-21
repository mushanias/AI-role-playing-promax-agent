"""追加式同步 Context 压缩测试。"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from typing import Mapping, Sequence

from app.models.conversation import (
    Branch,
    Conversation,
    SummaryVersion,
    Turn,
    TurnStatus,
)
from app.services.compressor import CompressionResult
from app.services.context_builder import ContextBuilder
from app.services.context_planner import ContextPlanner
from app.services.versioned_context_compression_service import (
    CompressionBatchPlanner,
    VersionedContextCompressionService,
)
from app.storage.conversation_repository import ConversationRepository


NOW = datetime.now(timezone.utc)


class FakeTokenCounter:
    """使用字符数模拟稳定的 Token 估算。"""

    @staticmethod
    def count_messages(
        messages: Sequence[Mapping[str, str]],
    ) -> int:
        return sum(len(message["content"]) for message in messages)


class RecordingCompressor:
    """记录请求并返回固定摘要。"""

    def __init__(self, summary: str = "新的版本摘要") -> None:
        self.summary = summary
        self.requests = []

    async def compress(self, request):
        self.requests.append(request)
        return CompressionResult(summary=self.summary)


class AdvancingCompressor(RecordingCompressor):
    """模拟压缩 LLM 调用期间目标分支继续前进。"""

    def __init__(
        self,
        repository: ConversationRepository,
        conversation_id: str,
    ) -> None:
        super().__init__()
        self.repository = repository
        self.conversation_id = conversation_id

    async def compress(self, request):
        result = await super().compress(request)

        def advance(conversation: Conversation) -> Conversation:
            branch = conversation.branches["branch-main"]
            late_turn = completed_turn(
                turn_id="turn-late",
                parent_turn_id=branch.head_turn_id,
                order=99,
            )
            conversation.turns[late_turn.turn_id] = late_turn
            branch.head_turn_id = late_turn.turn_id
            return conversation

        await self.repository.update(self.conversation_id, advance)
        return result


def completed_turn(
    turn_id: str,
    parent_turn_id: str | None,
    order: int,
) -> Turn:
    created_at = NOW + timedelta(seconds=order)
    return Turn(
        turn_id=turn_id,
        parent_turn_id=parent_turn_id,
        user_content="用" * 10,
        assistant_content="助" * 10,
        status=TurnStatus.COMPLETED,
        created_at=created_at,
        completed_at=created_at,
    )


def conversation_with_summary() -> Conversation:
    """创建摘要 A 覆盖第一轮、后接四轮原文的会话。"""
    turns = {}
    parent_turn_id = None
    for index in range(1, 6):
        turn = completed_turn(
            turn_id=f"turn-{index}",
            parent_turn_id=parent_turn_id,
            order=index,
        )
        turns[turn.turn_id] = turn
        parent_turn_id = turn.turn_id

    summary = SummaryVersion(
        summary_id="summary-a",
        covered_until_turn_id="turn-1",
        content="旧摘要",
        created_at=NOW + timedelta(seconds=10),
    )
    branch = Branch(
        branch_id="branch-main",
        head_turn_id="turn-5",
        active_summary_id="summary-a",
        created_at=NOW,
    )
    return Conversation(
        conversation_id="conversation-1",
        active_branch_id=branch.branch_id,
        turns=turns,
        branches={branch.branch_id: branch},
        summaries={summary.summary_id: summary},
    )


def build_services(
    repository: ConversationRepository,
    compressor,
    high_watermark: int = 60,
    low_watermark: int = 40,
    recent_raw_target: int = 20,
    min_summary_budget: int = 5,
):
    builder = ContextBuilder(
        token_counter=FakeTokenCounter(),
    )
    context_planner = ContextPlanner(
        context_builder=builder,
        high_watermark=high_watermark,
        low_watermark=low_watermark,
        recent_raw_token_target=recent_raw_target,
    )
    batch_planner = CompressionBatchPlanner(
        context_builder=builder,
        safety_margin=2,
        min_summary_token_budget=min_summary_budget,
    )
    service = VersionedContextCompressionService(
        repository=repository,
        context_planner=context_planner,
        batch_planner=batch_planner,
        compressor=compressor,
    )
    return context_planner, batch_planner, service


class VersionedCompressionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = ConversationRepository(
            self.temporary_directory.name
        )

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_batch_uses_complete_turn_boundary_and_raw_target(self) -> None:
        conversation = conversation_with_summary()
        compressor = RecordingCompressor()
        context_planner, batch_planner, _ = build_services(
            self.repository,
            compressor,
        )
        candidate = context_planner.build_candidate(
            conversation=conversation,
            profile={},
            branch_id="branch-main",
        )

        plan = batch_planner.plan(candidate, profile={})

        self.assertIsNotNone(plan)
        self.assertEqual(
            [turn.turn_id for turn in plan.turns_to_compress],
            ["turn-2", "turn-3", "turn-4"],
        )
        self.assertEqual(
            [turn.turn_id for turn in plan.raw_turns_to_keep],
            ["turn-5"],
        )
        self.assertLessEqual(
            plan.estimated_result_upper_bound,
            candidate.low_watermark,
        )

    async def test_compression_appends_summary_and_keeps_originals(self) -> None:
        conversation = conversation_with_summary()
        original_turn_dump = conversation.turns["turn-2"].model_dump()
        await self.repository.create(conversation)
        compressor = RecordingCompressor()
        _, _, service = build_services(self.repository, compressor)

        outcome = await service.compress_if_needed(
            conversation_id="conversation-1",
            branch_id="branch-main",
            profile={},
        )
        loaded = await self.repository.load("conversation-1")

        self.assertTrue(outcome.compressed)
        self.assertFalse(outcome.stale)
        self.assertIsNotNone(outcome.summary)
        self.assertEqual(
            outcome.summary.parent_summary_id,
            "summary-a",
        )
        self.assertEqual(
            outcome.summary.covered_until_turn_id,
            "turn-4",
        )
        self.assertIn("summary-a", loaded.summaries)
        self.assertIn(outcome.summary.summary_id, loaded.summaries)
        self.assertEqual(
            loaded.turns["turn-2"].model_dump(),
            original_turn_dump,
        )
        self.assertEqual(
            loaded.branches["branch-main"].active_summary_id,
            outcome.summary.summary_id,
        )
        self.assertEqual(
            [turn.turn_id for turn in outcome.candidate.plan.raw_turns],
            ["turn-5"],
        )
        self.assertEqual(len(compressor.requests), 1)
        self.assertEqual(len(compressor.requests[0].messages_to_compress), 6)

    async def test_stale_compression_result_is_discarded(self) -> None:
        await self.repository.create(conversation_with_summary())
        compressor = AdvancingCompressor(
            repository=self.repository,
            conversation_id="conversation-1",
        )
        _, _, service = build_services(self.repository, compressor)

        outcome = await service.compress_if_needed(
            conversation_id="conversation-1",
            branch_id="branch-main",
            profile={},
        )
        loaded = await self.repository.load("conversation-1")

        self.assertFalse(outcome.compressed)
        self.assertTrue(outcome.stale)
        self.assertEqual(set(loaded.summaries), {"summary-a"})
        self.assertEqual(
            loaded.branches["branch-main"].head_turn_id,
            "turn-late",
        )

    async def test_unavailable_compression_returns_warning(self) -> None:
        only_turn = completed_turn("turn-1", None, 1)
        branch = Branch(
            branch_id="branch-main",
            head_turn_id=only_turn.turn_id,
            created_at=NOW,
        )
        conversation = Conversation(
            conversation_id="conversation-1",
            active_branch_id=branch.branch_id,
            turns={only_turn.turn_id: only_turn},
            branches={branch.branch_id: branch},
        )
        await self.repository.create(conversation)
        compressor = RecordingCompressor()
        _, _, service = build_services(
            repository=self.repository,
            compressor=compressor,
            high_watermark=30,
            low_watermark=20,
            recent_raw_target=5,
            min_summary_budget=5,
        )

        outcome = await service.compress_if_needed(
            conversation_id="conversation-1",
            branch_id="branch-main",
            profile={"超长设定": "设" * 100},
        )

        self.assertFalse(outcome.compressed)
        self.assertIsNotNone(outcome.warning)
        self.assertEqual(len(compressor.requests), 0)


if __name__ == "__main__":
    unittest.main()
