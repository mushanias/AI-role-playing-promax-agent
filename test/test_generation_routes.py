"""后台生成启动、状态轮询与停止接口测试。"""

import asyncio
import time
import unittest

from fastapi.testclient import TestClient

from app.auth import require_local_user
from app.conversations.chat_stream import ChatStreamEvent
from app.conversations.generation_registry import GenerationRegistry
from app.core.dependencies import (
    get_conversation_service,
    get_generation_registry,
)
from app.main import app


class FakeGenerationConversationService:
    async def stream_message(
        self,
        conversation_id,
        user_input,
        generation_id,
        stop_event,
        branch_id=None,
    ):
        common = {
            "generation_id": generation_id,
            "conversation_id": conversation_id,
            "branch_id": branch_id or "branch-main",
            "turn_id": "turn-generation",
        }
        yield ChatStreamEvent(type="started", **common)
        await asyncio.sleep(0)
        yield ChatStreamEvent(type="delta", content="你好", **common)
        yield ChatStreamEvent(type="completed", duration_ms=120, **common)


class GenerationRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = GenerationRegistry()
        app.dependency_overrides[require_local_user] = lambda: "123456"
        app.dependency_overrides[get_conversation_service] = (
            lambda: FakeGenerationConversationService()
        )
        app.dependency_overrides[get_generation_registry] = (
            lambda: self.registry
        )
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()

    def test_start_and_poll_generation(self) -> None:
        response = self.client.post(
            "/conversations/conversation-1/turns/generations",
            json={
                "generation_id": "generation-1",
                "message": "你好",
                "branch_id": "branch-main",
            },
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "starting")

        payload = None
        for _ in range(50):
            status_response = self.client.get(
                "/generations/generation-1"
            )
            self.assertEqual(status_response.status_code, 200)
            payload = status_response.json()
            if payload["status"] == "completed":
                break
            time.sleep(0.01)

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["content"], "你好")
        self.assertEqual(payload["finish_reason"], "completed")

    def test_unknown_generation_returns_not_found(self) -> None:
        response = self.client.get("/generations/missing")

        self.assertEqual(response.status_code, 404)

    def test_stop_endpoint_sets_registered_signal(self) -> None:
        control = asyncio.run(
            self.registry.register("generation-stop", "conversation-1")
        )

        response = self.client.post(
            "/generations/generation-stop/stop"
        )

        self.assertEqual(response.status_code, 204)
        self.assertTrue(control.stop_event.is_set())


if __name__ == "__main__":
    unittest.main()
