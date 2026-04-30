from __future__ import annotations

import pytest
from jose import JWTError

from backend.core.security import (
    create_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)


def test_password_round_trip() -> None:
    hashed = hash_password("hunter2")
    assert verify_password("hunter2", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_password_hash_is_unique_per_call() -> None:
    assert hash_password("same") != hash_password("same")  # different salts


def test_needs_rehash_for_fresh_hash() -> None:
    assert needs_rehash(hash_password("x")) is False


def test_jwt_round_trip_access() -> None:
    token = create_token(42, "access", extra_claims={"foo": "bar"})
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "42"
    assert payload["type"] == "access"
    assert payload["foo"] == "bar"


def test_jwt_type_mismatch_raises() -> None:
    token = create_token(1, "access")
    with pytest.raises(JWTError):
        decode_token(token, expected_type="refresh")


def test_jwt_bad_signature_raises() -> None:
    token = create_token(1, "access")
    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    with pytest.raises(JWTError):
        decode_token(tampered)
