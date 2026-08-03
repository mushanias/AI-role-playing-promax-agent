"""LLM 模型目录与连接测试路由测试。"""

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.auth import require_local_user
from app.core.dependencies import get_versioned_llm_client
from app.main import app


class LLMRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[require_local_user] = lambda: "123456"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_list_presets_returns_requested_providers(self) -> None:
        response = self.client.get("/llm/presets")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["default_provider"], "minimax")
        self.assertEqual(body["default_model"], "MiniMax-M3")
        self.assertEqual(
            {provider["id"] for provider in body["providers"]},
            {"deepseek", "openai", "anthropic", "xai", "glm", "minimax"},
        )

    @patch(
        "app.llm.routes.LLMConnectionService.test_connection",
        new_callable=AsyncMock,
        return_value=True,
    )
    def test_custom_preset_connection(self, test_connection) -> None:
        response = self.client.post(
            "/llm/connection-test",
            json={
                "api_key": "secret",
                "custom_preset": {
                    "name": "自定义模型",
                    "sdk": "openai_chat",
                    "base_url": "https://example.com/v1",
                    "model": "custom-model",
                    "max_tokens": 1024,
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"success": True, "message": "连接成功"},
        )
        model = test_connection.await_args.args[0]
        self.assertEqual(model["request_params"]["model"], "custom-model")
        self.assertEqual(model["client_params"]["api_key"], "secret")

    @patch(
        "app.llm.routes.LLMConnectionService.test_connection",
        new_callable=AsyncMock,
        return_value=True,
    )
    def test_connection_without_selection_uses_default(self, test_connection) -> None:
        response = self.client.post(
            "/llm/connection-test",
            json={"api_key": "secret"},
        )

        self.assertEqual(response.status_code, 200)
        model = test_connection.await_args.args[0]
        self.assertEqual(model["provider"], "minimax")
        self.assertEqual(model["request_params"]["model"], "MiniMax-M3")

    @patch(
        "app.llm.routes.LLMConnectionService.test_connection",
        new_callable=AsyncMock,
        return_value=True,
    )
    def test_custom_preset_takes_priority_over_builtin(self, test_connection) -> None:
        response = self.client.post(
            "/llm/connection-test",
            json={
                "api_key": "secret",
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "custom_preset": {
                    "name": "优先使用的自定义模型",
                    "sdk": "anthropic",
                    "base_url": "https://example.com/anthropic",
                    "model": "custom-model",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        model = test_connection.await_args.args[0]
        self.assertEqual(model["provider"], "优先使用的自定义模型")
        self.assertEqual(model["request_params"]["model"], "custom-model")

    def test_get_active_model_never_exposes_api_key(self) -> None:
        class FakeRuntimeClient:
            @staticmethod
            def describe_active_model():
                return {
                    "provider": "minimax",
                    "model": "MiniMax-M3",
                    "connected": True,
                }

        app.dependency_overrides[get_versioned_llm_client] = (
            lambda: FakeRuntimeClient()
        )

        response = self.client.get("/llm/active")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "provider": "minimax",
                "model": "MiniMax-M3",
                "connected": True,
            },
        )
        self.assertNotIn("api_key", response.text)

    @patch(
        "app.llm.routes.LLMConnectionService.test_connection",
        new_callable=AsyncMock,
        return_value=True,
    )
    def test_activate_model_reconfigures_runtime_client(
        self,
        test_connection,
    ) -> None:
        runtime_client = type(
            "FakeRuntimeClient",
            (),
            {"reconfigure": AsyncMock()},
        )()
        app.dependency_overrides[get_versioned_llm_client] = (
            lambda: runtime_client
        )

        response = self.client.put(
            "/llm/active",
            json={
                "api_key": "secret",
                "provider": "glm",
                "model": "glm-5.2",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "success": True,
                "message": "连接成功，模型已启用",
                "provider": "glm",
                "model": "glm-5.2",
            },
        )
        activated_model = runtime_client.reconfigure.await_args.args[0]
        self.assertEqual(activated_model["provider"], "glm")
        self.assertEqual(
            activated_model["request_params"]["model"],
            "glm-5.2",
        )


if __name__ == "__main__":
    unittest.main()
