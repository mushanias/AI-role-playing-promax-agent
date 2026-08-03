"""单一本地账号密码、Session 与 HTTP 接口测试。"""

import unittest

from fastapi.testclient import TestClient

from app.auth.dependencies import get_local_auth_service
from app.auth.password import hash_password, verify_password
from app.auth.service import LocalAuthService
from app.main import app


class PasswordTests(unittest.TestCase):
    def test_scrypt_hash_round_trip(self) -> None:
        encoded = hash_password("123456", salt=b"fixed-test-salt")

        self.assertTrue(verify_password("123456", encoded))
        self.assertFalse(verify_password("wrong", encoded))
        self.assertNotIn("123456", encoded)


class AuthRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        password_hash = hash_password(
            "123456",
            salt=b"route-test-salt",
        )
        self.service = LocalAuthService(
            username="123456",
            password_hash=password_hash,
            session_ttl_seconds=3600,
        )
        app.dependency_overrides[get_local_auth_service] = (
            lambda: self.service
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_protected_route_requires_login(self) -> None:
        response = self.client.get("/conversations")

        self.assertEqual(response.status_code, 401)

    def test_login_session_and_logout(self) -> None:
        login_response = self.client.post(
            "/auth/login",
            json={"username": "123456", "password": "123456"},
        )

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json()["username"], "123456")
        self.assertIn("HttpOnly", login_response.headers["set-cookie"])

        session_response = self.client.get("/auth/session")
        self.assertEqual(session_response.status_code, 200)
        self.assertTrue(session_response.json()["authenticated"])

        logout_response = self.client.post("/auth/logout")
        self.assertEqual(logout_response.status_code, 204)
        self.assertEqual(self.client.get("/auth/session").status_code, 401)

    def test_login_rejects_wrong_password(self) -> None:
        response = self.client.post(
            "/auth/login",
            json={"username": "123456", "password": "wrong"},
        )

        self.assertEqual(response.status_code, 401)

    def test_login_rejects_unicode_username_without_server_error(self) -> None:
        response = self.client.post(
            "/auth/login",
            json={"username": "错误账号", "password": "123456"},
        )

        self.assertEqual(response.status_code, 401)
