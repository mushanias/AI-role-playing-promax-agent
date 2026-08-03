"""ConversationRepository 测试。"""

import asyncio
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from app.exceptions import (
    StorageConflictError,
    StorageCorruptionError,
    StorageNotFoundError,
)
from app.conversations.conversation import (
    Branch,
    Conversation,
    Turn,
    TurnStatus,
)
from app.conversations.conversation_repository import ConversationRepository


def empty_conversation(conversation_id: str) -> Conversation:
    """创建只有根分支的测试会话。"""
    branch = Branch(
        branch_id="branch-main",
        created_at=datetime.now(timezone.utc),
    )
    return Conversation(
        conversation_id=conversation_id,
        active_branch_id=branch.branch_id,
        branches={branch.branch_id: branch},
    )


class ConversationRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = ConversationRepository(
            self.temporary_directory.name
        )

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_create_and_load_round_trip(self) -> None:
        conversation = empty_conversation("conversation-1")

        await self.repository.create(conversation)
        loaded = await self.repository.load("conversation-1")

        self.assertTrue(await self.repository.exists("conversation-1"))
        self.assertEqual(loaded, conversation)

    async def test_create_rejects_existing_conversation(self) -> None:
        conversation = empty_conversation("conversation-1")
        await self.repository.create(conversation)

        with self.assertRaises(StorageConflictError):
            await self.repository.create(conversation)

    async def test_load_rejects_missing_conversation(self) -> None:
        with self.assertRaises(StorageNotFoundError):
            await self.repository.load("conversation-missing")

    async def test_save_rejects_missing_conversation(self) -> None:
        with self.assertRaises(StorageNotFoundError):
            await self.repository.save(
                empty_conversation("conversation-missing")
            )

    async def test_delete_moves_conversation_to_trash(self) -> None:
        await self.repository.create(empty_conversation("conversation-1"))
        before_delete = datetime.now(timezone.utc)

        await self.repository.delete("conversation-1")
        deleted = await self.repository.list_deleted()

        self.assertFalse(await self.repository.exists("conversation-1"))
        self.assertEqual(len(deleted), 1)
        self.assertEqual(
            deleted[0].conversation.conversation_id,
            "conversation-1",
        )
        self.assertGreaterEqual(deleted[0].deleted_at, before_delete)
        with self.assertRaises(StorageNotFoundError):
            await self.repository.delete("conversation-1")

    async def test_restore_moves_conversation_back_from_trash(self) -> None:
        original = empty_conversation("conversation-1")
        await self.repository.create(original)
        await self.repository.delete("conversation-1")

        await self.repository.restore("conversation-1")
        restored = await self.repository.load("conversation-1")

        self.assertEqual(restored, original)
        self.assertEqual(await self.repository.list_deleted(), [])

    async def test_restore_rejects_missing_deleted_conversation(self) -> None:
        with self.assertRaises(StorageNotFoundError):
            await self.repository.restore("conversation-missing")

    async def test_load_rejects_corrupted_model_data(self) -> None:
        file_path = os.path.join(
            self.temporary_directory.name,
            "conversation-broken.json",
        )
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(
                {
                    "schema_version": 1,
                    "conversation_id": "conversation-broken",
                    "active_branch_id": "missing-branch",
                    "turns": {},
                    "branches": {},
                    "summaries": {},
                },
                file,
            )

        with self.assertRaises(StorageCorruptionError):
            await self.repository.load("conversation-broken")

    async def test_update_saves_validated_snapshot(self) -> None:
        conversation = empty_conversation("conversation-1")
        await self.repository.create(conversation)

        def append_turn(current: Conversation) -> Conversation:
            turn = Turn(
                turn_id="turn-1",
                user_content="第一轮用户输入",
                assistant_content="第一轮助手回复",
                status=TurnStatus.COMPLETED,
                created_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            current.turns[turn.turn_id] = turn
            current.branches["branch-main"].head_turn_id = turn.turn_id
            return current

        updated = await self.repository.update(
            "conversation-1",
            append_turn,
        )
        loaded = await self.repository.load("conversation-1")

        self.assertEqual(updated, loaded)
        self.assertEqual(
            loaded.branches["branch-main"].head_turn_id,
            "turn-1",
        )

    async def test_concurrent_updates_do_not_lose_turns(self) -> None:
        conversation = empty_conversation("conversation-1")
        await self.repository.create(conversation)

        async def add_turn(turn_id: str) -> None:
            def updater(current: Conversation) -> Conversation:
                branch = current.branches["branch-main"]
                turn = Turn(
                    turn_id=turn_id,
                    parent_turn_id=branch.head_turn_id,
                    user_content=f"用户输入 {turn_id}",
                    assistant_content=f"助手回复 {turn_id}",
                    status=TurnStatus.COMPLETED,
                    created_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                )
                current.turns[turn.turn_id] = turn
                branch.head_turn_id = turn.turn_id
                return current

            await self.repository.update("conversation-1", updater)

        await asyncio.gather(
            add_turn("turn-a"),
            add_turn("turn-b"),
        )
        loaded = await self.repository.load("conversation-1")

        self.assertEqual(set(loaded.turns), {"turn-a", "turn-b"})
        head = loaded.branches["branch-main"].head_turn_id
        self.assertIsNotNone(head)
        parent = loaded.turns[head].parent_turn_id
        self.assertIsNotNone(parent)
        self.assertIn(parent, loaded.turns)

    async def test_rejects_unsafe_conversation_id(self) -> None:
        with self.assertRaises(ValueError):
            await self.repository.load("../outside")


if __name__ == "__main__":
    unittest.main()
