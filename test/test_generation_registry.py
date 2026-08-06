"""后台生成状态与停止注册表测试。"""

import unittest

from app.conversations.chat_stream import ChatStreamEvent
from app.conversations.generation_registry import GenerationRegistry
from app.exceptions import InvalidBranchOperationError


class GenerationRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_sets_signal_for_active_generation(self) -> None:
        registry = GenerationRegistry()
        control = await registry.register("generation-1", "conversation-1")

        self.assertTrue(await registry.request_stop("generation-1"))
        self.assertTrue(control.stop_event.is_set())

    async def test_delta_and_completion_remain_available_for_polling(
        self,
    ) -> None:
        registry = GenerationRegistry()
        control = await registry.register("generation-1", "conversation-1")
        common = {
            "generation_id": "generation-1",
            "conversation_id": "conversation-1",
            "branch_id": "branch-main",
            "turn_id": "turn-1",
        }

        await registry.apply_event(
            "generation-1",
            control,
            ChatStreamEvent(type="started", **common),
        )
        await registry.apply_event(
            "generation-1",
            control,
            ChatStreamEvent(type="delta", content="你好", **common),
        )
        await registry.apply_event(
            "generation-1",
            control,
            ChatStreamEvent(type="completed", duration_ms=120, **common),
        )

        snapshot = await registry.get_snapshot("generation-1")
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.status, "completed")
        self.assertEqual(snapshot.content, "你好")
        self.assertEqual(snapshot.finish_reason, "completed")
        self.assertFalse(await registry.request_stop("generation-1"))

    async def test_duplicate_generation_id_is_rejected(self) -> None:
        registry = GenerationRegistry()
        await registry.register("generation-1", "conversation-1")

        with self.assertRaises(InvalidBranchOperationError):
            await registry.register("generation-1", "conversation-1")


if __name__ == "__main__":
    unittest.main()
