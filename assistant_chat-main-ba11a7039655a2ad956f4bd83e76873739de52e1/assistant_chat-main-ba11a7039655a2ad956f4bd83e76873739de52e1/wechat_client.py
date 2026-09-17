"""Client for exchanging a Mini Program login code with WeChat."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests

CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
INVALID_CODE_ERRORS = {40029, 40163}


class WeChatLoginError(Exception):
    """A sanitized error returned to the Mini Program login endpoint."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class WeChatSession:
    openid: str
    unionid: Optional[str] = None


class WeChatClient:
    """Minimal code2Session client that never exposes session_key."""

    def __init__(
        self,
        *,
        appid: str,
        secret: str,
        session: Optional[requests.Session] = None,
    ) -> None:
        if (
            not appid
            or not secret
            or appid.startswith("replace-with")
            or secret.startswith("replace-with")
        ):
            raise RuntimeError("WECHAT_APPID and WECHAT_SECRET are required")
        self.appid = appid
        self._secret = secret
        self._session = session or requests.Session()

    def code2session(self, code: str) -> WeChatSession:
        if not code.strip():
            raise WeChatLoginError(422, "微信登录凭证不能为空")

        try:
            response = self._session.get(
                CODE2SESSION_URL,
                params={
                    "appid": self.appid,
                    "secret": self._secret,
                    "js_code": code,
                    "grant_type": "authorization_code",
                },
                timeout=(3.05, 10),
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise WeChatLoginError(502, "微信登录服务暂时不可用") from exc

        if not isinstance(payload, dict):
            raise WeChatLoginError(502, "微信登录服务返回异常")

        errcode = payload.get("errcode", 0)
        try:
            errcode = int(errcode)
        except (TypeError, ValueError):
            raise WeChatLoginError(502, "微信登录服务返回异常")

        if errcode in INVALID_CODE_ERRORS:
            raise WeChatLoginError(401, "微信登录凭证已失效，请重新登录")
        if errcode == 45011:
            raise WeChatLoginError(429, "微信登录请求过于频繁，请稍后重试")
        if errcode == -1:
            raise WeChatLoginError(503, "微信登录服务繁忙，请稍后重试")
        if errcode != 0:
            raise WeChatLoginError(502, "微信登录服务返回异常")

        openid = payload.get("openid")
        if not isinstance(openid, str) or not openid.strip():
            raise WeChatLoginError(502, "微信登录服务未返回用户标识")

        unionid = payload.get("unionid")
        return WeChatSession(
            openid=openid.strip(),
            unionid=unionid if isinstance(unionid, str) and unionid else None,
        )
