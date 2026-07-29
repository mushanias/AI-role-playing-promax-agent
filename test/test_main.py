"""应用入口的通用化配置测试。"""

import unittest

from app.main import app


class MainApplicationTests(unittest.TestCase):
    def test_application_uses_generic_identity(self) -> None:
        self.assertEqual(app.title, "版本化会话引擎")
        self.assertNotIn("角色", app.description)

    def test_profile_routes_are_removed(self) -> None:
        paths = set(app.openapi()["paths"])

        self.assertNotIn("/profile", paths)
        self.assertNotIn("/profile/setting", paths)
        self.assertIn("/conversations", paths)
        self.assertIn("/performance/data", paths)
        self.assertNotIn("/performance", paths)


if __name__ == "__main__":
    unittest.main()
