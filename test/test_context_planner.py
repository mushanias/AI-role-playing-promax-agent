"""ContextPlanner 与新 ContextBuilder 路径测试。"""

import unittest
from datetime import datetime, timedelta, timezone
from typing import Mapping, Sequence

from app.conversations.conversation import (
    Branch,
    Conversation,
    SummaryVersion,
    Turn,
    TurnStatus,
)
from app.conversations.memory.context_builder import ContextBuilder
from app.conversations.memory.context_planner import ContextPlanner


NOW = datetime.now(timezone.utc)


class FakeTokenCounter:
    """用字符数提供稳定、可预测的测试 Token 估算。"""

    @staticmethod
    def count_messages(
        messages: Sequence[Mapping[str, str]],
    ) -> int:
        return sum(len(message["content"]) for message in messages)


def completed_turn(
    turn_id: str,
    parent_turn_id: str | None,
    order: int,
) -> Turn:
    created_at = NOW + timedelta(seconds=order)
    return Turn(
        turn_id=turn_id,
        parent_turn_id=parent_turn_id,
        user_content=f"用户-{turn_id}",
        assistant_content=f"助手-{turn_id}",
        status=TurnStatus.COMPLETED,
        created_at=created_at,
        completed_at=created_at,
    )


def branched_conversation(
    active_summary_id: str | None = None,
    pending: bool = False,
) -> Conversation:
    """创建主线 1-2-3 和分支 1-alt 的测试会话。"""
    turn_1 = completed_turn("turn-1", None, 1)
    turn_2 = completed_turn("turn-2", "turn-1", 2)
    turn_3 = completed_turn("turn-3", "turn-2", 3)
    turn_alt = completed_turn("turn-alt", "turn-1", 4)
    turns = {
        turn.turn_id: turn
        for turn in (turn_1, turn_2, turn_3, turn_alt)
    }
    pending_turn_id = None

    if pending:
        pending_turn = Turn(
            turn_id="turn-pending",
            parent_turn_id="turn-3",
            user_content="当前用户输入",
            status=TurnStatus.PENDING,
            created_at=NOW + timedelta(seconds=5),
        )
        turns[pending_turn.turn_id] = pending_turn
        pending_turn_id = pending_turn.turn_id

    summary = SummaryVersion(
        summary_id="summary-a",
        covered_until_turn_id="turn-1",
        content="第一轮历史摘要",
        created_at=NOW + timedelta(seconds=6),
    )
    main_branch = Branch(
        branch_id="branch-main",
        head_turn_id="turn-3",
        pending_turn_id=pending_turn_id,
        active_summary_id=active_summary_id,
        created_at=NOW,
    )
    alt_branch = Branch(
        branch_id="branch-alt",
        parent_branch_id="branch-main",
        forked_from_turn_id="turn-1",
        head_turn_id="turn-alt",
        created_at=NOW + timedelta(seconds=4),
    )
    return Conversation(
        conversation_id="conversation-1",
        active_branch_id="branch-main",
        turns=turns,
        branches={
            main_branch.branch_id: main_branch,
            alt_branch.branch_id: alt_branch,
        },
        summaries={summary.summary_id: summary},
    )


def planner(high_watermark: int = 1000) -> ContextPlanner:
    builder = ContextBuilder(
        token_counter=FakeTokenCounter(),
    )
    return ContextPlanner(
        context_builder=builder,
        high_watermark=high_watermark,
        low_watermark=max(2, high_watermark // 2),
        recent_raw_token_target=1,
    )


class ContextPlannerTests(unittest.TestCase):
    def test_active_branch_path_excludes_other_story_branch(self) -> None:
        candidate = planner().build_candidate(
            conversation=branched_conversation(),
        )

        self.assertEqual(
            [turn.turn_id for turn in candidate.plan.raw_turns],
            ["turn-1", "turn-2", "turn-3"],
        )
        message_contents = [
            message["content"] for message in candidate.messages
        ]
        self.assertFalse(
            any("turn-alt" in content for content in message_contents)
        )

    def test_explicit_branch_id_builds_alternative_path(self) -> None:
        candidate = planner().build_candidate(
            conversation=branched_conversation(),
            branch_id="branch-alt",
        )

        self.assertEqual(
            [turn.turn_id for turn in candidate.plan.raw_turns],
            ["turn-1", "turn-alt"],
        )

    def test_summary_removes_covered_turns_from_raw_context(self) -> None:
        candidate = planner().build_candidate(
            conversation=branched_conversation(
                active_summary_id="summary-a"
            ),
        )

        self.assertEqual(candidate.plan.summary.summary_id, "summary-a")
        self.assertEqual(
            [turn.turn_id for turn in candidate.plan.raw_turns],
            ["turn-2", "turn-3"],
        )
        self.assertEqual(candidate.messages[0]["role"], "system")
        self.assertIn("【历史摘要】\n第一轮历史摘要", candidate.messages[0]["content"])

    def test_pending_turn_is_last_message_not_raw_turn(self) -> None:
        candidate = planner().build_candidate(
            conversation=branched_conversation(pending=True),
        )

        self.assertNotIn(
            "turn-pending",
            [turn.turn_id for turn in candidate.plan.raw_turns],
        )
        self.assertEqual(
            candidate.plan.pending_turn.turn_id,
            "turn-pending",
        )
        self.assertEqual(candidate.messages[-1], {
            "role": "user",
            "content": "当前用户输入",
        })

    def test_candidate_uses_actual_messages_for_watermark(self) -> None:
        conversation = branched_conversation()
        small_candidate = planner(high_watermark=1000).build_candidate(
            conversation=conversation,
        )
        large_candidate = planner(high_watermark=10).build_candidate(
            conversation=conversation,
        )

        self.assertFalse(small_candidate.needs_compression)
        self.assertTrue(large_candidate.needs_compression)
        self.assertGreater(large_candidate.estimated_tokens, 10)

    def test_builder_preserves_turn_message_order(self) -> None:
        candidate = planner().build_candidate(
            conversation=branched_conversation(),
        )

        self.assertEqual(
            [message["role"] for message in candidate.messages],
            [
                "user",
                "assistant",
                "user",
                "assistant",
                "user",
                "assistant",
            ],
        )

    def test_watermark_configuration_requires_room_for_raw_tail(self) -> None:
        builder = ContextBuilder(
            token_counter=FakeTokenCounter(),
        )

        with self.assertRaises(ValueError):
            ContextPlanner(
                context_builder=builder,
                high_watermark=100,
                low_watermark=50,
                recent_raw_token_target=50,
            )


if __name__ == "__main__":
    unittest.main()
