"""分支化 ContextManager 编排测试。"""

import tempfile
import unittest
from datetime import datetime, timezone

from app.conversations.conversation import (
    Branch,
    Conversation,
    Turn,
    TurnStatus,
)
from app.conversations.conversation_repository import ConversationRepository
from app.conversations.memory.compression_plan import (
    VersionedCompressionOutcome,
)
from app.conversations.memory.context_builder import ContextBuilder
from app.conversations.memory.context_plan import ContextCandidate
from app.conversations.memory.context_planner import ContextPlanner
from app.conversations.memory.versioned_context_manager import (
    VersionedContextManager,
)


NOW = datetime.now(timezone.utc)


class FakeTokenCounter:
    """使用字符数模拟稳定的 Token 估算。"""

    @staticmethod
    def count_messages(messages) -> int:
        return sum(len(message["content"]) for message in messages)


class RecordingCompressionService:
    """按顺序返回预设结果的压缩服务。"""

    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls = []

    async def compress_if_needed(
        self,
        conversation_id,
        branch_id,
        prefix_messages=(),
    ):
        self.calls.append((conversation_id, branch_id))
        if not self.outcomes:
            raise AssertionError("压缩调用次数超过测试预期")
        return self.outcomes.pop(0)


def completed_turn(
    turn_id: str,
    parent_turn_id: str | None,
    content_size: int,
) -> Turn:
    return Turn(
        turn_id=turn_id,
        parent_turn_id=parent_turn_id,
        user_content="用" * content_size,
        assistant_content="助" * content_size,
        status=TurnStatus.COMPLETED,
        created_at=NOW,
        completed_at=NOW,
    )


def build_conversation() -> Conversation:
    root_turn = completed_turn("turn-root", None, 10)
    main_turn = completed_turn("turn-main", root_turn.turn_id, 10)
    other_turn = completed_turn("turn-other", root_turn.turn_id, 2)
    main_branch = Branch(
        branch_id="branch-main",
        head_turn_id=main_turn.turn_id,
        created_at=NOW,
    )
    other_branch = Branch(
        branch_id="branch-other",
        head_turn_id=other_turn.turn_id,
        created_at=NOW,
    )
    return Conversation(
        conversation_id="conversation-1",
        active_branch_id=main_branch.branch_id,
        turns={
            root_turn.turn_id: root_turn,
            main_turn.turn_id: main_turn,
            other_turn.turn_id: other_turn,
        },
        branches={
            main_branch.branch_id: main_branch,
            other_branch.branch_id: other_branch,
        },
    )


def build_candidate(
    conversation: Conversation,
    branch_id: str,
    needs_compression: bool,
) -> ContextCandidate:
    builder = ContextBuilder(FakeTokenCounter())
    planner = ContextPlanner(
        context_builder=builder,
        high_watermark=30,
        low_watermark=20,
        recent_raw_token_target=10,
    )
    candidate = planner.build_candidate(
        conversation=conversation,
        branch_id=branch_id,
    )
    return ContextCandidate(
        plan=candidate.plan,
        messages=candidate.messages,
        estimated_tokens=candidate.estimated_tokens,
        high_watermark=candidate.high_watermark,
        low_watermark=candidate.low_watermark,
        recent_raw_token_target=candidate.recent_raw_token_target,
        needs_compression=needs_compression,
    )


class VersionedContextManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = ConversationRepository(
            self.temporary_directory.name
        )
        self.conversation = build_conversation()
        await self.repository.create(self.conversation)
        self.builder = ContextBuilder(
            FakeTokenCounter(),
        )

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    def build_manager(self, compression_service, high_watermark=100):
        planner = ContextPlanner(
            context_builder=self.builder,
            high_watermark=high_watermark,
            low_watermark=20,
            recent_raw_token_target=10,
        )
        return VersionedContextManager(
            repository=self.repository,
            context_planner=planner,
            compression_service=compression_service,
            max_compression_passes=2,
        )

    async def test_below_high_watermark_skips_compression(self) -> None:
        compression_service = RecordingCompressionService([])
        manager = self.build_manager(compression_service)

        result = await manager.build("conversation-1")

        self.assertEqual(result.compression_passes, 0)
        self.assertFalse(result.quality_degraded)
        self.assertEqual(compression_service.calls, [])
        self.assertEqual(result.candidate.plan.branch_id, "branch-main")

    async def test_prefix_is_injected_once_before_conversation(self) -> None:
        class PrefixProvider:
            async def get_messages(self, request):
                return ({"role": "system", "content": "固定事实"},)

        compression_service = RecordingCompressionService([])
        manager = self.build_manager(compression_service)
        manager.prefix_provider = PrefixProvider()

        result = await manager.build("conversation-1")

        self.assertEqual(result.messages[0]["content"], "固定事实")
        self.assertEqual(
            sum(
                message["content"] == "固定事实"
                for message in result.messages
            ),
            1,
        )

    async def test_explicit_branch_id_selects_target_branch(self) -> None:
        compression_service = RecordingCompressionService([])
        manager = self.build_manager(compression_service)

        result = await manager.build(
            "conversation-1",
            branch_id="branch-other",
        )

        self.assertEqual(result.candidate.plan.branch_id, "branch-other")
        self.assertEqual(
            [turn.turn_id for turn in result.candidate.plan.raw_turns],
            ["turn-root", "turn-other"],
        )

    async def test_compression_repeats_until_candidate_is_below_high(self) -> None:
        high_candidate = build_candidate(
            self.conversation,
            "branch-main",
            needs_compression=True,
        )
        low_candidate = build_candidate(
            self.conversation,
            "branch-main",
            needs_compression=False,
        )
        compression_service = RecordingCompressionService([
            VersionedCompressionOutcome(
                candidate=high_candidate,
                summary=None,
                compressed=True,
                stale=False,
                warning=None,
            ),
            VersionedCompressionOutcome(
                candidate=low_candidate,
                summary=None,
                compressed=True,
                stale=False,
                warning=None,
            ),
        ])
        manager = self.build_manager(
            compression_service,
            high_watermark=30,
        )

        result = await manager.build("conversation-1")

        self.assertEqual(result.compression_passes, 2)
        self.assertFalse(result.quality_degraded)
        self.assertEqual(len(compression_service.calls), 2)

    async def test_unavailable_compression_returns_warning(self) -> None:
        high_candidate = build_candidate(
            self.conversation,
            "branch-main",
            needs_compression=True,
        )
        compression_service = RecordingCompressionService([
            VersionedCompressionOutcome(
                candidate=high_candidate,
                summary=None,
                compressed=False,
                stale=False,
                warning="当前没有可安全压缩的完整轮次。",
            )
        ])
        manager = self.build_manager(
            compression_service,
            high_watermark=30,
        )

        result = await manager.build("conversation-1")

        self.assertTrue(result.quality_degraded)
        self.assertEqual(result.compression_passes, 1)
        self.assertIn(
            "当前没有可安全压缩的完整轮次。",
            result.warnings,
        )
        self.assertTrue(
            any("降级 Context" in warning for warning in result.warnings)
        )
        self.assertIsNotNone(result.degraded_messages)
        self.assertLessEqual(result.estimated_tokens, 30)

        loaded = await self.repository.load("conversation-1")
        self.assertEqual(set(loaded.turns), set(self.conversation.turns))

    async def test_maximum_passes_returns_degraded_context(self) -> None:
        high_candidate = build_candidate(
            self.conversation,
            "branch-main",
            needs_compression=True,
        )
        compression_service = RecordingCompressionService([
            VersionedCompressionOutcome(
                candidate=high_candidate,
                summary=None,
                compressed=True,
                stale=False,
                warning=None,
            ),
            VersionedCompressionOutcome(
                candidate=high_candidate,
                summary=None,
                compressed=True,
                stale=False,
                warning=None,
            ),
        ])
        manager = self.build_manager(
            compression_service,
            high_watermark=30,
        )

        result = await manager.build("conversation-1")

        self.assertEqual(result.compression_passes, 2)
        self.assertTrue(result.quality_degraded)
        self.assertTrue(
            any("最大压缩次数" in warning for warning in result.warnings)
        )


if __name__ == "__main__":
    unittest.main()
