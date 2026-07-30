"""学习 Agent 命令与增量契约测试。"""

import unittest
from datetime import UTC, datetime

from pydantic import ValidationError

from app.learning.contracts.commands import (
    ActivePathContext,
    CompactBranch,
    CompactGraph,
    ConversationAction,
    ConversationCommand,
    PromptSnapshot,
    RuntimeModelConfig,
    StableContext,
)
from app.learning.contracts.delta import ConversationDelta
from app.learning.domain.models import ConnectionKind, LearningTurn


NOW = datetime(2026, 7, 30, tzinfo=UTC)


def empty_graph() -> CompactGraph:
    return CompactGraph(
        conversation_id="conversation-1",
        revision=0,
        main_branch_id="branch-main",
        branches=(CompactBranch(branch_id="branch-main"),),
    )


def root_command(**changes) -> ConversationCommand:
    values = {
        "operation_id": "operation-1",
        "expected_revision": 0,
        "action": ConversationAction.CREATE_ROOT,
        "goal_id": "goal-1",
        "conversation_id": "conversation-1",
        "new_turn_id": "turn-1",
        "user_text": "请规划我的学习路径",
        "compact_graph": empty_graph(),
        "active_path_context": ActivePathContext(),
        "stable_context": StableContext(
            background="零基础",
            learning_goal="学习高等数学",
            target_level="能够参加研究生考试",
        ),
        "prompt_snapshot": PromptSnapshot(
            prompt_id="prompt-1",
            name="默认学习助手",
            source="builtin",
            version=1,
            content="你是一个学习助手。",
        ),
        "runtime_model": RuntimeModelConfig(
            provider="openai",
            model="gpt-test",
        ),
    }
    values.update(changes)
    return ConversationCommand(**values)


class ConversationCommandTests(unittest.TestCase):
    def test_root_command_accepts_empty_graph(self) -> None:
        command = root_command()

        self.assertEqual(command.expected_revision, 0)
        self.assertEqual(command.retrieval_mode.value, "auto")

    def test_command_rejects_revision_mismatch(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "expected_revision",
        ):
            root_command(expected_revision=1)

    def test_root_command_rejects_branch_fields(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "创建根节点",
        ):
            root_command(source_turn_id="turn-old")


class ConversationDeltaTests(unittest.TestCase):
    def test_delta_requires_one_revision_and_one_turn(self) -> None:
        turn = LearningTurn(
            turn_id="turn-1",
            connection_kind=ConnectionKind.ROOT,
            user_content="问题",
            assistant_content="回答",
            provider="openai",
            model="gpt-test",
            created_at=NOW,
        )

        delta = ConversationDelta(
            operation_id="operation-1",
            old_revision=0,
            new_revision=1,
            added_turns=(turn,),
            next_active_branch_id="branch-main",
            next_active_head_turn_id="turn-1",
        )

        self.assertEqual(delta.added_turns[0].turn_id, "turn-1")

    def test_delta_rejects_revision_jump(self) -> None:
        turn = LearningTurn(
            turn_id="turn-1",
            connection_kind=ConnectionKind.ROOT,
            user_content="问题",
            assistant_content="回答",
            provider="openai",
            model="gpt-test",
            created_at=NOW,
        )

        with self.assertRaisesRegex(ValidationError, "revision"):
            ConversationDelta(
                operation_id="operation-1",
                old_revision=0,
                new_revision=2,
                added_turns=(turn,),
                next_active_branch_id="branch-main",
                next_active_head_turn_id="turn-1",
            )


if __name__ == "__main__":
    unittest.main()

