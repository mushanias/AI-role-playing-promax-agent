"""应用入口的通用化配置测试。"""

import unittest

from fastapi.testclient import TestClient

from app.main import app


class MainApplicationTests(unittest.TestCase):
    def test_application_uses_learning_product_identity(self) -> None:
        self.assertEqual(app.title, "学习路径 Agent API")
        self.assertIn("公共知识库", app.description)

    def test_profile_routes_are_removed(self) -> None:
        paths = set(app.openapi()["paths"])

        self.assertNotIn("/profile", paths)
        self.assertNotIn("/profile/setting", paths)
        self.assertIn("/conversations", paths)
        self.assertIn("/performance/data", paths)
        self.assertNotIn("/performance", paths)

    def test_local_frontend_origin_can_send_api_key_header(self) -> None:
        response = TestClient(app).options(
            "/learning/conversations/turns",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": (
                    "content-type,x-provider-api-key"
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://127.0.0.1:5173",
        )


if __name__ == "__main__":
    unittest.main()
