"""Unit tests for JWT and Server-owned Agent identity."""

from __future__ import annotations

import os
import unittest
from datetime import timedelta

from fastapi import HTTPException

os.environ.setdefault(
    "DATABASE_URL",
    "mysql+pymysql://test:test@127.0.0.1:3306/test?charset=utf8mb4",
)
os.environ.setdefault("AUTH_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
os.environ.setdefault("WECHAT_APPID", "wx-test")
os.environ.setdefault("WECHAT_SECRET", "wechat-test-secret")

from auth import User, create_access_token, verify_token  # noqa: E402
from passwords import hash_password, verify_password  # noqa: E402
from server import _build_agent_identity, app  # noqa: E402


class AuthTest(unittest.TestCase):
    def test_access_token_round_trip(self) -> None:
        token = create_access_token("user-id-1")

        token_data = verify_token(token)

        self.assertIsNotNone(token_data)
        self.assertEqual(token_data.user_id, "user-id-1")

    def test_expired_token_is_rejected(self) -> None:
        token = create_access_token("user-id-1", expires_delta=timedelta(seconds=-1))

        self.assertIsNone(verify_token(token))

    def test_patient_token_round_trip(self) -> None:
        token = create_access_token("patient-1", auth_method="patient")

        token_data = verify_token(token)

        self.assertIsNotNone(token_data)
        self.assertEqual(token_data.user_id, "patient-1")
        self.assertEqual(token_data.auth_method, "patient")

    def test_password_is_salted_and_verifiable(self) -> None:
        first = hash_password("SecretPassword123")
        second = hash_password("SecretPassword123")

        self.assertNotEqual(first, second)
        self.assertNotIn("SecretPassword123", first)
        self.assertTrue(verify_password("SecretPassword123", first))
        self.assertFalse(verify_password("wrong-password", first))

    def test_agent_identity_uses_authenticated_user_and_normalized_uuid(self) -> None:
        user = User(id="server-user-id")
        agent_user, agent_thread = _build_agent_identity(
            user,
            "550E8400-E29B-41D4-A716-446655440000",
        )

        self.assertEqual(agent_user, "mp:server-user-id")
        self.assertEqual(
            agent_thread,
            "mp:server-user-id:550e8400-e29b-41d4-a716-446655440000",
        )

    def test_agent_identity_rejects_invalid_thread_id(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            _build_agent_identity(User(id="server-user-id"), "not-a-uuid")

        self.assertEqual(raised.exception.status_code, 422)

    def test_openapi_exposes_both_login_methods(self) -> None:
        paths = app.openapi()["paths"]

        self.assertIn("/api/auth/wechat", paths)
        self.assertIn("/api/auth/login", paths)
        self.assertIn("/api/auth/register", paths)


if __name__ == "__main__":
    unittest.main()
