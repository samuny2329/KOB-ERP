"""Password hashing (argon2) + JWT encode/decode helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from backend.config import get_settings

_hasher = PasswordHasher()
_settings = get_settings()


def hash_password(plain: str) -> str:
    """Argon2id hash; returns a self-describing string suitable for storage."""
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time verify; rehash transparently if params changed.

    Returns False on mismatch, True on success.  Caller can use
    ``needs_rehash(hashed)`` afterwards to decide whether to re-hash.
    """
    try:
        _hasher.verify(hashed, plain)
        return True
    except VerifyMismatchError:
        return False


def needs_rehash(hashed: str) -> bool:
    return _hasher.check_needs_rehash(hashed)


TokenType = Literal["access", "refresh"]


def create_token(
    subject: str | int,
    token_type: TokenType,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT.  ``subject`` is typically the user id."""
    now = datetime.now(UTC)
    if token_type == "access":
        expires = now + timedelta(minutes=_settings.access_token_expire_minutes)
    else:
        expires = now + timedelta(days=_settings.refresh_token_expire_days)

    claims: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    if extra_claims:
        claims.update(extra_claims)

    return jwt.encode(claims, _settings.secret_key, algorithm=_settings.jwt_algorithm)


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    """Decode and validate a JWT.

    Raises ``JWTError`` on bad signature / expired token / type mismatch.
    """
    payload: dict[str, Any] = jwt.decode(
        token,
        _settings.secret_key,
        algorithms=[_settings.jwt_algorithm],
    )
    if expected_type and payload.get("type") != expected_type:
        raise JWTError(f"expected token type {expected_type!r}, got {payload.get('type')!r}")
    return payload
