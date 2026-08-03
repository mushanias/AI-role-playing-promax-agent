"""会话历史数据模型测试。"""

import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from app.conversations.conversation import (
    Branch,
    Conversation,
    SummaryVersion,
    Turn,
    TurnStatus,
)


NOW = datetime.now(timezone.utc)


def completed_turn(
    turn_id: str,
    parent_turn_id: str | None = None,
) -> Turn:
    """创建测试用的完成轮次。"""
    return Turn(
        turn_id=turn_id,
        parent_turn_id=parent_turn_id,
        user_content=f"用户输入 {turn_id}",
        assistant_content=f"助手回复 {turn_id}",
        status=TurnStatus.COMPLETED,
        created_at=NOW,
        completed_at=NOW,
    )


class TurnModelTests(unittest.TestCase):
    def test_completed_turn_requires_assistant_content(self) -> None:
        with self.assertRaises(ValidationError):
            Turn(
                turn_id="turn-1",
                user_content="用户输入",
                status=TurnStatus.COMPLETED,
                created_at=NOW,
                completed_at=NOW,
            )

    def test_pending_turn_cannot_have_assistant_reply(self) -> None:
        with self.assertRaises(ValidationError):
            Turn(
                turn_id="turn-1",
                user_content="用户输入",
                assistant_content="不应存在的助手回复",
                status=TurnStatus.PENDING,
                created_at=NOW,
            )

    def test_pending_turn_cannot_have_response_duration(self) -> None:
        with self.assertRaises(ValidationError):
            Turn(
                turn_id="turn-1",
                user_content="用户输入",
                status=TurnStatus.PENDING,
                created_at=NOW,
                response_duration_ms=100,
            )

    def test_completed_turn_accepts_response_duration(self) -> None:
        turn = Turn(
            turn_id="turn-1",
            user_content="用户输入",
            assistant_content="助手回复",
            status=TurnStatus.COMPLETED,
            created_at=NOW,
            completed_at=NOW,
            response_duration_ms=1250,
        )

        self.assertEqual(turn.response_duration_ms, 1250)


class ConversationModelTests(unittest.TestCase):
    def test_valid_conversation_with_pending_turn(self) -> None:
        turn_1 = completed_turn("turn-1")
        turn_2 = Turn(
            turn_id="turn-2",
            parent_turn_id="turn-1",
            user_content="新的用户输入",
            status=TurnStatus.PENDING,
            created_at=NOW,
        )
        summary = SummaryVersion(
            summary_id="summary-1",
            covered_until_turn_id="turn-1",
            content="第一轮摘要",
            created_at=NOW,
        )
        branch = Branch(
            branch_id="branch-main",
            head_turn_id="turn-1",
            pending_turn_id="turn-2",
            active_summary_id="summary-1",
            created_at=NOW,
        )

        conversation = Conversation(
            conversation_id="conversation-1",
            active_branch_id="branch-main",
            turns={"turn-1": turn_1, "turn-2": turn_2},
            branches={"branch-main": branch},
            summaries={"summary-1": summary},
        )

        self.assertEqual(conversation.active_branch_id, "branch-main")

    def test_rejects_missing_parent_turn(self) -> None:
        orphan = completed_turn("turn-2", parent_turn_id="turn-missing")
        branch = Branch(
            branch_id="branch-main",
            head_turn_id="turn-2",
            created_at=NOW,
        )

        with self.assertRaises(ValidationError):
            Conversation(
                conversation_id="conversation-1",
                active_branch_id="branch-main",
                turns={"turn-2": orphan},
                branches={"branch-main": branch},
            )

    def test_valid_branch_can_advance_after_fork_point(self) -> None:
        turn_1 = completed_turn("turn-1")
        turn_2 = completed_turn("turn-2", "turn-1")
        alternative_turn = completed_turn("turn-alt", "turn-1")
        main_branch = Branch(
            branch_id="branch-main",
            head_turn_id="turn-2",
            created_at=NOW,
        )
        alternative_branch = Branch(
            branch_id="branch-alt",
            parent_branch_id="branch-main",
            forked_from_turn_id="turn-1",
            head_turn_id="turn-alt",
            created_at=NOW,
        )

        conversation = Conversation(
            conversation_id="conversation-1",
            active_branch_id="branch-alt",
            turns={
                "turn-1": turn_1,
                "turn-2": turn_2,
                "turn-alt": alternative_turn,
            },
            branches={
                "branch-main": main_branch,
                "branch-alt": alternative_branch,
            },
        )

        self.assertEqual(
            conversation.branches["branch-alt"].head_turn_id,
            "turn-alt",
        )

    def test_branch_forked_from_root_can_own_new_root_turn(self) -> None:
        original_turn = completed_turn("turn-original")
        alternative_root = completed_turn("turn-alternative-root")
        alternative_child = completed_turn(
            "turn-alternative-child",
            "turn-alternative-root",
        )
        original_branch = Branch(
            branch_id="branch-original",
            head_turn_id="turn-original",
            created_at=NOW,
        )
        alternative_branch = Branch(
            branch_id="branch-alternative",
            parent_branch_id="branch-original",
            forked_from_turn_id=None,
            head_turn_id="turn-alternative-child",
            created_at=NOW,
        )

        conversation = Conversation(
            conversation_id="conversation-1",
            active_branch_id="branch-alternative",
            turns={
                "turn-original": original_turn,
                "turn-alternative-root": alternative_root,
                "turn-alternative-child": alternative_child,
            },
            branches={
                "branch-original": original_branch,
                "branch-alternative": alternative_branch,
            },
        )

        self.assertEqual(
            conversation.branches["branch-alternative"].head_turn_id,
            "turn-alternative-child",
        )

    def test_branch_forked_from_root_rejects_parent_history(self) -> None:
        original_turn = completed_turn("turn-original")
        child_turn = completed_turn("turn-child", "turn-original")
        original_branch = Branch(
            branch_id="branch-original",
            head_turn_id="turn-child",
            created_at=NOW,
        )
        invalid_branch = Branch(
            branch_id="branch-invalid",
            parent_branch_id="branch-original",
            forked_from_turn_id=None,
            head_turn_id="turn-child",
            created_at=NOW,
        )

        with self.assertRaises(ValidationError):
            Conversation(
                conversation_id="conversation-1",
                active_branch_id="branch-invalid",
                turns={
                    "turn-original": original_turn,
                    "turn-child": child_turn,
                },
                branches={
                    "branch-original": original_branch,
                    "branch-invalid": invalid_branch,
                },
            )

    def test_rejects_summary_from_other_turn_branch(self) -> None:
        turn_1 = completed_turn("turn-1")
        turn_2 = completed_turn("turn-2", "turn-1")
        other_turn = completed_turn("turn-other", "turn-1")
        summary = SummaryVersion(
            summary_id="summary-other",
            covered_until_turn_id="turn-other",
            content="另一条会话分支的摘要",
            created_at=NOW,
        )
        branch = Branch(
            branch_id="branch-main",
            head_turn_id="turn-2",
            active_summary_id="summary-other",
            created_at=NOW,
        )

        with self.assertRaises(ValidationError):
            Conversation(
                conversation_id="conversation-1",
                active_branch_id="branch-main",
                turns={
                    "turn-1": turn_1,
                    "turn-2": turn_2,
                    "turn-other": other_turn,
                },
                branches={"branch-main": branch},
                summaries={"summary-other": summary},
            )

    def test_rejects_turn_cycle(self) -> None:
        turn_1 = completed_turn("turn-1", "turn-2")
        turn_2 = completed_turn("turn-2", "turn-1")
        branch = Branch(
            branch_id="branch-main",
            head_turn_id="turn-2",
            created_at=NOW,
        )

        with self.assertRaises(ValidationError):
            Conversation(
                conversation_id="conversation-1",
                active_branch_id="branch-main",
                turns={"turn-1": turn_1, "turn-2": turn_2},
                branches={"branch-main": branch},
            )

    def test_turn_parent_must_be_completed(self) -> None:
        pending_parent = Turn(
            turn_id="turn-pending",
            user_content="尚未完成",
            status=TurnStatus.PENDING,
            created_at=NOW,
        )
        child = completed_turn("turn-child", "turn-pending")
        branch = Branch(
            branch_id="branch-main",
            head_turn_id="turn-child",
            created_at=NOW,
        )

        with self.assertRaises(ValidationError):
            Conversation(
                conversation_id="conversation-1",
                active_branch_id="branch-main",
                turns={
                    "turn-pending": pending_parent,
                    "turn-child": child,
                },
                branches={"branch-main": branch},
            )

    def test_child_summary_must_extend_parent_history(self) -> None:
        turn_1 = completed_turn("turn-1")
        turn_2 = completed_turn("turn-2", "turn-1")
        turn_3 = completed_turn("turn-3", "turn-1")
        summary_1 = SummaryVersion(
            summary_id="summary-1",
            covered_until_turn_id="turn-2",
            content="主线摘要",
            created_at=NOW,
        )
        summary_2 = SummaryVersion(
            summary_id="summary-2",
            parent_summary_id="summary-1",
            covered_until_turn_id="turn-3",
            content="错误继承的摘要",
            created_at=NOW,
        )
        branch = Branch(
            branch_id="branch-main",
            head_turn_id="turn-2",
            created_at=NOW,
        )

        with self.assertRaises(ValidationError):
            Conversation(
                conversation_id="conversation-1",
                active_branch_id="branch-main",
                turns={
                    "turn-1": turn_1,
                    "turn-2": turn_2,
                    "turn-3": turn_3,
                },
                branches={"branch-main": branch},
                summaries={
                    "summary-1": summary_1,
                    "summary-2": summary_2,
                },
            )


if __name__ == "__main__":
    unittest.main()
