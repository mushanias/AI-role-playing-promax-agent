"""学习会话图不变量和端口策略测试。"""

import unittest
from datetime import UTC, datetime

from pydantic import ValidationError

from app.exceptions.learning_errors import LearningGraphRuleError
from app.learning.contracts.commands import ConversationAction
from app.learning.domain.graph_policy import LearningGraphPolicy
from app.learning.domain.models import (
    ConnectionKind,
    LearningBranch,
    LearningConversation,
    LearningTurn,
    NodePort,
)


NOW = datetime(2026, 7, 30, tzinfo=UTC)


def turn(
    turn_id: str,
    parent_turn_id: str | None,
    kind: ConnectionKind,
    port: NodePort | None,
) -> LearningTurn:
    return LearningTurn(
        turn_id=turn_id,
        parent_turn_id=parent_turn_id,
        connection_kind=kind,
        parent_port=port,
        user_content=f"问题 {turn_id}",
        assistant_content=f"回答 {turn_id}",
        provider="test",
        model="test-model",
        created_at=NOW,
    )


def conversation_with_vertical_path() -> LearningConversation:
    turns = {
        "turn-1": turn(
            "turn-1",
            None,
            ConnectionKind.ROOT,
            None,
        ),
        "turn-2": turn(
            "turn-2",
            "turn-1",
            ConnectionKind.CONTINUE,
            NodePort.BOTTOM,
        ),
        "turn-3": turn(
            "turn-3",
            "turn-2",
            ConnectionKind.CONTINUE,
            NodePort.BOTTOM,
        ),
    }
    return LearningConversation(
        conversation_id="conversation-1",
        revision=3,
        main_branch_id="branch-main",
        root_turn_id="turn-1",
        turns=turns,
        branches={
            "branch-main": LearningBranch(
                branch_id="branch-main",
                head_turn_id="turn-3",
                created_at=NOW,
            )
        },
    )


class LearningConversationTests(unittest.TestCase):
    def test_valid_vertical_path(self) -> None:
        conversation = conversation_with_vertical_path()

        self.assertTrue(conversation.is_ancestor("turn-1", "turn-3"))

    def test_root_rejects_multiple_children(self) -> None:
        conversation = conversation_with_vertical_path()
        values = conversation.model_dump(mode="python")
        values["turns"]["turn-extra"] = turn(
            "turn-extra",
            "turn-1",
            ConnectionKind.CONTINUE,
            NodePort.RIGHT,
        )

        with self.assertRaisesRegex(ValidationError, "端口|根节点"):
            LearningConversation.model_validate(values)

    def test_rejects_duplicate_parent_port(self) -> None:
        conversation = conversation_with_vertical_path()
        values = conversation.model_dump(mode="python")
        values["turns"]["turn-4"] = turn(
            "turn-4",
            "turn-2",
            ConnectionKind.FORK,
            NodePort.BOTTOM,
        )

        with self.assertRaisesRegex(ValidationError, "端口"):
            LearningConversation.model_validate(values)

    def test_rejects_branch_without_turn(self) -> None:
        conversation = conversation_with_vertical_path()
        values = conversation.model_dump(mode="python")
        values["turns"]["turn-4"] = turn(
            "turn-4",
            "turn-2",
            ConnectionKind.FORK,
            NodePort.RIGHT,
        )
        values["branches"]["branch-right"] = LearningBranch(
            branch_id="branch-right",
            parent_branch_id="branch-main",
            forked_from_turn_id="turn-2",
            head_turn_id="turn-3",
            created_at=NOW,
        )

        with self.assertRaisesRegex(ValidationError, "第一条连接"):
            LearningConversation.model_validate(values)


class LearningGraphPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = LearningGraphPolicy()

    def test_create_root_only_accepts_empty_conversation(self) -> None:
        empty = LearningConversation(
            conversation_id="conversation-empty",
            revision=0,
            main_branch_id="branch-main",
            branches={
                "branch-main": LearningBranch(
                    branch_id="branch-main",
                    created_at=NOW,
                )
            },
        )

        placement = self.policy.plan(
            empty,
            ConversationAction.CREATE_ROOT,
            source_turn_id=None,
            branch_id=None,
        )

        self.assertEqual(placement.connection_kind, ConnectionKind.ROOT)
        self.assertIsNone(placement.parent_port)

    def test_root_cannot_fork(self) -> None:
        conversation = conversation_with_vertical_path()

        with self.assertRaisesRegex(
            LearningGraphRuleError,
            "根节点",
        ):
            self.policy.plan(
                conversation,
                ConversationAction.FORK_FROM_TURN,
                source_turn_id="turn-1",
                branch_id="branch-main",
            )

    def test_append_requires_branch_head(self) -> None:
        conversation = conversation_with_vertical_path()

        with self.assertRaisesRegex(
            LearningGraphRuleError,
            "分支末端",
        ):
            self.policy.plan(
                conversation,
                ConversationAction.APPEND_TURN,
                source_turn_id="turn-2",
                branch_id="branch-main",
            )

    def test_vertical_fork_chooses_right_first(self) -> None:
        conversation = conversation_with_vertical_path()

        placement = self.policy.plan(
            conversation,
            ConversationAction.FORK_FROM_TURN,
            source_turn_id="turn-2",
            branch_id="branch-main",
        )

        self.assertEqual(placement.connection_kind, ConnectionKind.FORK)
        self.assertEqual(placement.parent_port, NodePort.RIGHT)

    def test_second_vertical_fork_uses_other_side(self) -> None:
        conversation = conversation_with_vertical_path()
        values = conversation.model_dump(mode="python")
        values["turns"]["turn-right"] = turn(
            "turn-right",
            "turn-2",
            ConnectionKind.FORK,
            NodePort.RIGHT,
        )
        values["branches"]["branch-right"] = LearningBranch(
            branch_id="branch-right",
            parent_branch_id="branch-main",
            forked_from_turn_id="turn-2",
            head_turn_id="turn-right",
            created_at=NOW,
        )
        conversation = LearningConversation.model_validate(values)

        placement = self.policy.plan(
            conversation,
            ConversationAction.FORK_FROM_TURN,
            source_turn_id="turn-2",
            branch_id="branch-main",
        )

        self.assertEqual(placement.parent_port, NodePort.LEFT)

    def test_full_turn_has_no_more_fork_ports(self) -> None:
        conversation = conversation_with_vertical_path()
        values = conversation.model_dump(mode="python")
        for name, port in (
            ("right", NodePort.RIGHT),
            ("left", NodePort.LEFT),
        ):
            turn_id = f"turn-{name}"
            branch_id = f"branch-{name}"
            values["turns"][turn_id] = turn(
                turn_id,
                "turn-2",
                ConnectionKind.FORK,
                port,
            )
            values["branches"][branch_id] = LearningBranch(
                branch_id=branch_id,
                parent_branch_id="branch-main",
                forked_from_turn_id="turn-2",
                head_turn_id=turn_id,
                created_at=NOW,
            )
        conversation = LearningConversation.model_validate(values)

        with self.assertRaisesRegex(
            LearningGraphRuleError,
            "没有可用",
        ):
            self.policy.plan(
                conversation,
                ConversationAction.FORK_FROM_TURN,
                source_turn_id="turn-2",
                branch_id="branch-main",
            )


if __name__ == "__main__":
    unittest.main()
