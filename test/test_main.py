"""应用入口的通用化配置测试。"""

import asyncio
import json
import unittest

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app, unexpected_exception_handler


class MainApplicationTests(unittest.TestCase):
    def test_application_uses_generic_identity(self) -> None:
        self.assertEqual(app.title, "版本化会话引擎")
        self.assertNotIn("角色", app.description)

    def test_profile_routes_are_removed(self) -> None:
        paths = set(app.openapi()["paths"])

        self.assertNotIn("/profile", paths)
        self.assertNotIn("/profile/setting", paths)
        self.assertIn("/conversations", paths)
        self.assertIn(
            "delete",
            app.openapi()["paths"]["/conversations/{conversation_id}"],
        )
        self.assertIn("/conversations/trash", paths)
        self.assertIn(
            "/conversations/trash/{conversation_id}/restore",
            paths,
        )
        self.assertIn("/performance/data", paths)
        self.assertNotIn("/performance", paths)

    def test_local_frontend_origin_is_allowed(self) -> None:
        response = TestClient(app).options(
            "/llm/presets",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://127.0.0.1:5173",
        )
        self.assertEqual(
            response.headers["access-control-allow-credentials"],
            "true",
        )
        self.assertIn(
            "DELETE",
            response.headers["access-control-allow-methods"],
        )

    def test_unexpected_error_uses_stable_json_response(self) -> None:
        request = type(
            "RequestStub",
            (),
            {
                "method": "POST",
                "url": type("UrlStub", (), {"path": "/test"})(),
            },
        )()

        response = self._run_async(
            unexpected_exception_handler(
                request,
                RuntimeError("内部细节不应暴露"),
            )
        )
        payload = json.loads(response.body)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            payload["error"]["code"],
            "internal_server_error",
        )
        self.assertNotIn("内部细节不应暴露", payload["error"]["message"])

    def test_unexpected_error_keeps_cors_header(self) -> None:
        async def raise_unexpected_error() -> None:
            raise RuntimeError("测试异常")

        route = APIRoute(
            "/__unexpected-error-test",
            raise_unexpected_error,
            methods=["GET"],
        )
        app.router.routes.append(route)

        try:
            response = TestClient(
                app,
                raise_server_exceptions=False,
            ).get(
                "/__unexpected-error-test",
                headers={"Origin": "http://127.0.0.1:5173"},
            )
        finally:
            app.router.routes.remove(route)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://127.0.0.1:5173",
        )
        self.assertEqual(
            response.json()["error"]["code"],
            "internal_server_error",
        )

    @staticmethod
    def _run_async(awaitable):
        return asyncio.run(awaitable)


if __name__ == "__main__":
    unittest.main()
