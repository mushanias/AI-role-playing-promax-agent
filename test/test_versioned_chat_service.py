"""版本化 ChatService 与 Turn 生命周期测试。"""

import tempfile
import unittest
from datetime import datetime, timezone

from app.exceptions import InvalidBranchOperationError, LLMNetworkError
from app.conversations.conversation import (
    Branch,
    Conversation,
    Turn,
    TurnStatus,
)
from app.conversations.conversation_repository import ConversationRepository
from app.conversations.memory.context_builder import ContextBuilder
from app.conversations.memory.context_plan import ManagedContext
from app.conversations.memory.context_planner import ContextPlanner
from app.conversations.versioned_chat_service import VersionedChatService


NOW = datetime.now(timezone.utc)


class FakeTokenCounter:
    @staticmethod
    def count_messages(messages) -> int:
        return sum(len(message["content"]) for message in messages)


class InspectingContextManager:
    """构建真实候选，并确认主 LLM 前 pending 已经落盘。"""

    def __init__(
        self,
        repository: ConversationRepository,
        warnings=(),
    ) -> None:
        self.repository = repository
        self.warnings = tuple(warnings)
        self.calls = []
        builder = ContextBuilder(FakeTokenCounter())
        self.planner = ContextPlanner(
            context_builder=builder,
            high_watermark=800,
            low_watermark=600,
            recent_raw_token_target=200,
        )

    async def build(self, conversation_id, branch_id=None):
        conversation = await self.repository.load(conversation_id)
        branch = conversation.branches[branch_id]
        if branch.pending_turn_id is None:
            raise AssertionError("Context 构建前 pending Turn 尚未落盘")
        pending_turn = conversation.turns[branch.pending_turn_id]
        if pending_turn.status != TurnStatus.PENDING:
            raise AssertionError("Context 当前输入不是 pending Turn")

        self.calls.append((conversation_id, branch_id))
        candidate = self.planner.build_candidate(
            conversation=conversation,
            branch_id=branch_id,
        )
        return ManagedContext(
            candidate=candidate,
            warnings=self.warnings,
            compression_passes=1 if self.warnings else 0,
        )


class FakeLLMClient:
    def __init__(self, reply="助手回复", error=None) -> None:
        self.reply = reply
        self.error = error
        self.messages = None

    async def chat(self, messages):
        self.messages = messages
        if self.error is not None:
            raise self.error
        return self.reply


class FakePerformanceSink:
    def __init__(self, error=None) -> None:
        self.error = error
        self.records = []

    async def record(self, **record) -> None:
        if self.error is not None:
            raise self.error
        self.records.append(record)


def initial_conversation() -> Conversation:
    first_turn = Turn(
        turn_id="turn-1",
        user_content="第一问",
        assistant_content="第一答",
        status=TurnStatus.COMPLETED,
        created_at=NOW,
        completed_at=NOW,
    )
    main_branch = Branch(
        branch_id="branch-main",
        head_turn_id=first_turn.turn_id,
        created_at=NOW,
    )
    other_branch = Branch(
        branch_id="branch-other",
        created_at=NOW,
    )
    return Conversation(
        conversation_id="conversation-1",
        active_branch_id=main_branch.branch_id,
        turns={first_turn.turn_id: first_turn},
        branches={
            main_branch.branch_id: main_branch,
            other_branch.branch_id: other_branch,
        },
    )


class VersionedChatServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = ConversationRepository(
            self.temporary_directory.name
        )
        await self.repository.create(initial_conversation())

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    def build_service(
        self,
        llm_client,
        warnings=(),
        performance_sink=None,
    ):
        context_manager = InspectingContextManager(
            repository=self.repository,
            warnings=warnings,
        )
        service = VersionedChatService(
            repository=self.repository,
            llm_client=llm_client,
            context_manager=context_manager,
            performance_sink=performance_sink,
        )
        return service, context_manager

    async def test_success_completes_turn_and_advances_head(self) -> None:
        llm_client = FakeLLMClient(reply="第二答")
        service, context_manager = self.build_service(
            llm_client,
            warnings=("上下文质量下降",),
        )

        result = await service.send(
            conversation_id="conversation-1",
            user_input="第二问",
        )
        loaded = await self.repository.load("conversation-1")
        turn = loaded.turns[result.turn_id]
        branch = loaded.branches["branch-main"]

        self.assertEqual(context_manager.calls, [
            ("conversation-1", "branch-main")
        ])
        self.assertEqual(turn.parent_turn_id, "turn-1")
        self.assertEqual(turn.user_content, "第二问")
        self.assertEqual(turn.assistant_content, "第二答")
        self.assertEqual(turn.status, TurnStatus.COMPLETED)
        self.assertEqual(branch.head_turn_id, result.turn_id)
        self.assertIsNone(branch.pending_turn_id)
        self.assertEqual(result.warnings, ("上下文质量下降",))
        self.assertTrue(result.quality_degraded)
        self.assertEqual(
            llm_client.messages[-1],
            {"role": "user", "content": "第二问"},
        )

    async def test_success_records_performance_metrics(self) -> None:
        performance_sink = FakePerformanceSink()
        service, _ = self.build_service(
            FakeLLMClient(),
            warnings=("上下文质量下降",),
            performance_sink=performance_sink,
        )

        await service.send(
            conversation_id="conversation-1",
            user_input="第二问",
        )

        self.assertEqual(len(performance_sink.records), 1)
        record = performance_sink.records[0]
        self.assertEqual(record["conversation_id"], "conversation-1")
        self.assertEqual(record["branch_id"], "branch-main")
        self.assertGreaterEqual(record["total_ms"], record["llm_ms"])
        self.assertGreaterEqual(record["total_ms"], record["context_ms"])
        self.assertGreater(record["input_tokens"], 0)
        self.assertEqual(record["compression_passes"], 1)
        self.assertTrue(record["quality_degraded"])

    async def test_performance_failure_does_not_fail_chat(self) -> None:
        performance_sink = FakePerformanceSink(
            error=OSError("磁盘暂不可用")
        )
        service, _ = self.build_service(
            FakeLLMClient(reply="仍然成功"),
            performance_sink=performance_sink,
        )

        result = await service.send(
            conversation_id="conversation-1",
            user_input="第二问",
        )
        loaded = await self.repository.load("conversation-1")

        self.assertEqual(result.reply, "仍然成功")
        self.assertEqual(
            loaded.turns[result.turn_id].status,
            TurnStatus.COMPLETED,
        )

    async def test_llm_failure_preserves_failed_turn(self) -> None:
        llm_error = LLMNetworkError("网络失败")
        service, _ = self.build_service(
            FakeLLMClient(error=llm_error)
        )

        with self.assertRaises(LLMNetworkError):
            await service.send(
                conversation_id="conversation-1",
                user_input="不会丢失的输入",
            )

        loaded = await self.repository.load("conversation-1")
        failed_turns = [
            turn
            for turn in loaded.turns.values()
            if turn.status == TurnStatus.FAILED
        ]
        self.assertEqual(len(failed_turns), 1)
        self.assertEqual(
            failed_turns[0].user_content,
            "不会丢失的输入",
        )
        self.assertIn("LLMNetworkError", failed_turns[0].failure_message)
        self.assertEqual(
            loaded.branches["branch-main"].head_turn_id,
            "turn-1",
        )
        self.assertIsNone(
            loaded.branches["branch-main"].pending_turn_id
        )

    async def test_send_to_other_branch_does_not_move_active_branch(self) -> None:
        service, _ = self.build_service(FakeLLMClient())

        result = await service.send(
            conversation_id="conversation-1",
            user_input="另一条分支消息",
            branch_id="branch-other",
        )
        loaded = await self.repository.load("conversation-1")

        self.assertEqual(result.branch_id, "branch-other")
        self.assertEqual(
            loaded.branches["branch-other"].head_turn_id,
            result.turn_id,
        )
        self.assertEqual(
            loaded.branches["branch-main"].head_turn_id,
            "turn-1",
        )
        self.assertEqual(loaded.active_branch_id, "branch-main")

    async def test_existing_pending_rejects_second_turn(self) -> None:
        existing_pending = Turn(
            turn_id="turn-pending",
            parent_turn_id="turn-1",
            user_content="正在生成",
            status=TurnStatus.PENDING,
            created_at=NOW,
        )

        def add_pending(conversation: Conversation) -> Conversation:
            conversation.turns[existing_pending.turn_id] = existing_pending
            conversation.branches[
                "branch-main"
            ].pending_turn_id = existing_pending.turn_id
            return conversation

        await self.repository.update("conversation-1", add_pending)
        llm_client = FakeLLMClient()
        service, context_manager = self.build_service(llm_client)

        with self.assertRaises(InvalidBranchOperationError):
            await service.send(
                conversation_id="conversation-1",
                user_input="并发输入",
            )

        loaded = await self.repository.load("conversation-1")
        self.assertEqual(set(loaded.turns), {"turn-1", "turn-pending"})
        self.assertEqual(context_manager.calls, [])
        self.assertIsNone(llm_client.messages)


if __name__ == "__main__":
    unittest.main()
