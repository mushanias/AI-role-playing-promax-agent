"""不变事实的 JSON 存储、Context 前缀与 HTTP 接口测试。"""

import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.auth import require_local_user
from app.context import ContextPrefixRequest
from app.core.dependencies import get_fact_set_service
from app.fact_sets.context_provider import FactSetContextProvider
from app.fact_sets.repository import FactSetRepository
from app.fact_sets.service import FactSetService
from app.main import app


class FactSetRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.file_path = os.path.join(
            self.temporary_directory.name,
            "fact_sets",
            "default.json",
        )
        self.repository = FactSetRepository(self.file_path)

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_missing_file_returns_empty_fact_set(self) -> None:
        fact_set = await self.repository.load()

        self.assertEqual(fact_set.content, "")
        self.assertIsNone(fact_set.updated_at)

    async def test_replace_persists_single_document(self) -> None:
        saved = await self.repository.replace("默认使用中文回答。")
        loaded = await self.repository.load()

        self.assertEqual(loaded, saved)
        with open(self.file_path, "r", encoding="utf-8") as file:
            raw = json.load(file)
        self.assertEqual(raw["schema_version"], 1)
        self.assertEqual(raw["content"], "默认使用中文回答。")

    async def test_empty_content_disables_context_prefix(self) -> None:
        service = FactSetService(self.repository)
        provider = FactSetContextProvider(service)

        messages = await provider.get_messages(
            ContextPrefixRequest("conversation-1", None)
        )
        self.assertEqual(messages, ())

        await service.replace("事实 A")
        messages = await provider.get_messages(
            ContextPrefixRequest("conversation-1", "branch-main")
        )
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("事实 A", messages[0]["content"])


class FactSetRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        repository = FactSetRepository(
            os.path.join(self.temporary_directory.name, "default.json")
        )
        self.service = FactSetService(repository)
        app.dependency_overrides[require_local_user] = lambda: "local-user"
        app.dependency_overrides[get_fact_set_service] = lambda: self.service
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.temporary_directory.cleanup()

    def test_get_put_and_clear_fact_set(self) -> None:
        empty = self.client.get("/fact-set")
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json(), {"content": "", "updated_at": None})

        saved = self.client.put(
            "/fact-set",
            json={"content": "事实 A\n事实 B"},
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["content"], "事实 A\n事实 B")
        self.assertIsNotNone(saved.json()["updated_at"])
        self.assertEqual(
            self.client.get("/fact-set").json()["content"],
            "事实 A\n事实 B",
        )

        cleared = self.client.put("/fact-set", json={"content": ""})
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.json()["content"], "")


if __name__ == "__main__":
    unittest.main()
