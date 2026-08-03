"""新版后端从会话创建到压缩、重写和切换的端到端测试。"""

import tempfile
import unittest

from app.conversations.branch_service import BranchService
from app.conversations.conversation_repository import ConversationRepository
from app.conversations.conversation_service import ConversationService
from app.conversations.memory.context_builder import ContextBuilder
from app.conversations.memory.context_planner import ContextPlanner
from app.conversations.memory.llm_compressor import LLMCompressor
from app.conversations.memory.versioned_context_compression_service import (
    CompressionBatchPlanner,
    VersionedContextCompressionService,
)
from app.conversations.memory.versioned_context_manager import (
    VersionedContextManager,
)
from app.conversations.versioned_chat_service import VersionedChatService


class CharacterTokenCounter:
    """使用字符数提供完全可预测的端到端预算。"""

    @staticmethod
    def count_messages(messages) -> int:
        return sum(len(message["content"]) for message in messages)


class ScenarioLLMClient:
    """区分摘要调用和主聊天调用，并记录实际发送载荷。"""

    def __init__(self) -> None:
        self.chat_payloads = []
        self.compression_calls = 0

    async def chat(self, messages):
        if any(
            "待压缩对话" in message["content"]
            for message in messages
        ):
            self.compression_calls += 1
            return "稳定摘要"

        self.chat_payloads.append(messages)
        return f"主回复{len(self.chat_payloads)}"


async def build_backend(
    base_directory: str,
    high_watermark: int,
    low_watermark: int,
    recent_raw_target: int,
):
    repository = ConversationRepository(
        f"{base_directory}/conversations"
    )
    llm_client = ScenarioLLMClient()
    context_builder = ContextBuilder(
        token_counter=CharacterTokenCounter(),
    )
    context_planner = ContextPlanner(
        context_builder=context_builder,
        high_watermark=high_watermark,
        low_watermark=low_watermark,
        recent_raw_token_target=recent_raw_target,
    )
    compression_service = VersionedContextCompressionService(
        repository=repository,
        context_planner=context_planner,
        batch_planner=CompressionBatchPlanner(
            context_builder=context_builder,
            safety_margin=2,
            min_summary_token_budget=5,
        ),
        compressor=LLMCompressor(llm_client),
    )
    context_manager = VersionedContextManager(
        repository=repository,
        context_planner=context_planner,
        compression_service=compression_service,
        max_compression_passes=3,
    )
    chat_service = VersionedChatService(
        repository=repository,
        llm_client=llm_client,
        context_manager=context_manager,
    )
    conversation_service = ConversationService(
        repository=repository,
        branch_service=BranchService(repository),
        chat_service=chat_service,
    )
    return conversation_service, repository, llm_client


class BackendEndToEndTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_compress_rewrite_switch_and_original_retention(self) -> None:
        service, repository, llm_client = await build_backend(
            self.temporary_directory.name,
            high_watermark=70,
            low_watermark=45,
            recent_raw_target=20,
        )
        conversation = await service.create_conversation()
        original_results = []

        for index in range(1, 6):
            result = await service.send_message(
                conversation_id=conversation.conversation_id,
                user_input=str(index) * 12,
            )
            original_results.append(result)

        compressed = await repository.load(conversation.conversation_id)
        original_branch_id = compressed.active_branch_id
        original_head_id = compressed.branches[
            original_branch_id
        ].head_turn_id
        self.assertGreaterEqual(llm_client.compression_calls, 1)
        self.assertGreaterEqual(len(compressed.summaries), 1)
        self.assertEqual(len(compressed.turns), 5)

        target_result = original_results[2]
        rewritten = await service.rewrite_turn(
            conversation_id=conversation.conversation_id,
            target_turn_id=target_result.turn_id,
            user_input="修改第三轮",
            source_branch_id=original_branch_id,
        )
        after_rewrite = await repository.load(conversation.conversation_id)

        self.assertNotEqual(rewritten.branch_id, original_branch_id)
        self.assertEqual(
            after_rewrite.branches[original_branch_id].head_turn_id,
            original_head_id,
        )
        self.assertIn(target_result.turn_id, after_rewrite.turns)
        self.assertEqual(
            after_rewrite.turns[rewritten.turn_id].parent_turn_id,
            original_results[1].turn_id,
        )

        variants = await service.list_turn_variants(
            conversation.conversation_id,
            target_result.turn_id,
        )
        self.assertEqual(
            {variant.turn_id for variant in variants},
            {target_result.turn_id, rewritten.turn_id},
        )

        await service.activate_branch(
            conversation.conversation_id,
            original_branch_id,
        )
        restored_history = await service.get_history(
            conversation.conversation_id
        )
        self.assertEqual(
            restored_history.turns[-1].turn_id,
            original_results[-1].turn_id,
        )

    async def test_extreme_input_degrades_payload_but_keeps_json(self) -> None:
        service, repository, llm_client = await build_backend(
            self.temporary_directory.name,
            high_watermark=30,
            low_watermark=20,
            recent_raw_target=10,
        )
        conversation = await service.create_conversation()
        original_input = "极" * 100

        result = await service.send_message(
            conversation_id=conversation.conversation_id,
            user_input=original_input,
        )
        loaded = await repository.load(conversation.conversation_id)
        stored_turn = loaded.turns[result.turn_id]
        sent_payload = llm_client.chat_payloads[-1]
        sent_tokens = CharacterTokenCounter.count_messages(sent_payload)

        self.assertTrue(result.quality_degraded)
        self.assertTrue(any("截短" in warning for warning in result.warnings))
        self.assertLessEqual(sent_tokens, 30)
        self.assertNotEqual(sent_payload[-1]["content"], original_input)
        self.assertEqual(stored_turn.user_content, original_input)

    async def test_rewrite_first_turn_creates_working_root_branch(self) -> None:
        service, repository, _ = await build_backend(
            self.temporary_directory.name,
            high_watermark=100,
            low_watermark=80,
            recent_raw_target=40,
        )
        conversation = await service.create_conversation()
        original = await service.send_message(
            conversation_id=conversation.conversation_id,
            user_input="原始第一问",
        )

        rewritten = await service.rewrite_turn(
            conversation_id=conversation.conversation_id,
            target_turn_id=original.turn_id,
            user_input="修改后的第一问",
        )
        continued = await service.send_message(
            conversation_id=conversation.conversation_id,
            user_input="新分支的第二问",
        )
        loaded = await repository.load(conversation.conversation_id)
        history = await service.get_history(conversation.conversation_id)

        self.assertNotEqual(rewritten.branch_id, original.branch_id)
        self.assertEqual(loaded.active_branch_id, rewritten.branch_id)
        self.assertIsNone(
            loaded.turns[rewritten.turn_id].parent_turn_id
        )
        self.assertEqual(
            loaded.branches[rewritten.branch_id].head_turn_id,
            continued.turn_id,
        )
        self.assertEqual(
            loaded.turns[continued.turn_id].parent_turn_id,
            rewritten.turn_id,
        )
        self.assertEqual(
            [turn.user_content for turn in history.turns],
            ["修改后的第一问", "新分支的第二问"],
        )


if __name__ == "__main__":
    unittest.main()
