"""Unit tests for WeChat code2Session error mapping."""

from __future__ import annotations

import unittest

import requests

from wechat_client import WeChatClient, WeChatLoginError


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


class FakeSession:
    def __init__(self, payload: object = None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.params = None
        self.timeout = None

    def get(self, url: str, *, params: dict, timeout: tuple[float, int]) -> FakeResponse:
        if self.error:
            raise self.error
        self.params = params
        self.timeout = timeout
        return FakeResponse(self.payload)


class WeChatClientTest(unittest.TestCase):
    def make_client(self, session: FakeSession) -> WeChatClient:
        return WeChatClient(appid="wx-test", secret="secret", session=session)

    def test_success_returns_identity_without_session_key(self) -> None:
        session = FakeSession(
            {"openid": "openid-1", "unionid": "unionid-1", "session_key": "sensitive"}
        )

        result = self.make_client(session).code2session("code-1")

        self.assertEqual(result.openid, "openid-1")
        self.assertEqual(result.unionid, "unionid-1")
        self.assertFalse(hasattr(result, "session_key"))
        self.assertEqual(session.params["secret"], "secret")
        self.assertEqual(session.timeout, (3.05, 10))

    def test_invalid_code_maps_to_401(self) -> None:
        for errcode in (40029, 40163):
            with self.subTest(errcode=errcode):
                with self.assertRaises(WeChatLoginError) as raised:
                    self.make_client(FakeSession({"errcode": errcode})).code2session("bad")
                self.assertEqual(raised.exception.status_code, 401)

    def test_rate_limit_maps_to_429(self) -> None:
        with self.assertRaises(WeChatLoginError) as raised:
            self.make_client(FakeSession({"errcode": 45011})).code2session("code")
        self.assertEqual(raised.exception.status_code, 429)

    def test_busy_maps_to_503(self) -> None:
        with self.assertRaises(WeChatLoginError) as raised:
            self.make_client(FakeSession({"errcode": -1})).code2session("code")
        self.assertEqual(raised.exception.status_code, 503)

    def test_unknown_or_malformed_response_maps_to_502(self) -> None:
        for payload in ({"errcode": 99999}, [], {"session_key": "missing-openid"}):
            with self.subTest(payload=payload):
                with self.assertRaises(WeChatLoginError) as raised:
                    self.make_client(FakeSession(payload)).code2session("code")
                self.assertEqual(raised.exception.status_code, 502)

    def test_transport_error_maps_to_502(self) -> None:
        with self.assertRaises(WeChatLoginError) as raised:
            self.make_client(FakeSession(error=requests.Timeout())).code2session("code")
        self.assertEqual(raised.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
