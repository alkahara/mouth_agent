"""bcrypt password hashing compatible with existing patient accounts."""

from __future__ import annotations

import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, encoded: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), encoded.encode("ascii"))
    except (TypeError, ValueError):
        return False
