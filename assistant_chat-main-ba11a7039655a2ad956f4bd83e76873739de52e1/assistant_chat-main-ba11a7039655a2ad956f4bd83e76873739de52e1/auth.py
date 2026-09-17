"""JWT authentication for WeChat and patient Server users."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from user_repository import USER_STATUS_ACTIVE, UserRepository


def _required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


SECRET_KEY = _required_setting("AUTH_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("AUTH_TOKEN_EXPIRE_MINUTES", "1440"))
AUTH_ISSUER = os.getenv("AUTH_ISSUER", "assistant-chat").strip()
AUTH_AUDIENCE = os.getenv("AUTH_AUDIENCE", "sanora-mini-program").strip()

if len(SECRET_KEY) < 32 or SECRET_KEY.startswith("replace-with") or SECRET_KEY == (
    "assistant-chat-secret-key-change-in-production"
):
    raise RuntimeError("AUTH_SECRET_KEY must be replaced with a strong random secret")
if ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
    raise RuntimeError("AUTH_TOKEN_EXPIRE_MINUTES must be positive")
if not AUTH_ISSUER or not AUTH_AUDIENCE:
    raise RuntimeError("AUTH_ISSUER and AUTH_AUDIENCE are required")

security = HTTPBearer(auto_error=False)


class User(BaseModel):
    """Authenticated user returned to Server endpoints."""

    id: str
    login_type: str = "wechat"


class TokenUser(BaseModel):
    id: str
    login_type: str = "wechat"


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: TokenUser


class TokenData(BaseModel):
    user_id: str
    auth_method: str


def create_access_token(
    user_id: str,
    expires_delta: Optional[timedelta] = None,
    auth_method: str = "wechat",
) -> str:
    """Create a signed JWT for an internal user ID."""

    if auth_method not in ("wechat", "patient"):
        raise ValueError("Unsupported authentication method")

    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": user_id,
        "iss": AUTH_ISSUER,
        "aud": AUTH_AUDIENCE,
        "auth_method": auth_method,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[TokenData]:
    """Verify a JWT and return its internal user ID."""

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            audience=AUTH_AUDIENCE,
            issuer=AUTH_ISSUER,
        )
    except JWTError:
        return None

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        return None
    auth_method = payload.get("auth_method")
    if auth_method not in ("wechat", "patient"):
        return None
    return TokenData(user_id=user_id, auth_method=auth_method)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the current active user from a Server JWT."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证令牌",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise credentials_exception

    token_data = verify_token(credentials.credentials)
    if token_data is None:
        raise credentials_exception

    repository = UserRepository(db)
    user = repository.get_by_id(token_data.user_id)
    if user is None:
        raise credentials_exception
    if user.status != USER_STATUS_ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    if token_data.auth_method == "patient":
        patient = repository.get_patient_by_user_id(user.id)
        if patient is None or patient.status != USER_STATUS_ACTIVE:
            raise credentials_exception

    return User(id=user.id, login_type=token_data.auth_method)
