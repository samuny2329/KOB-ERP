"""Authentication dependencies + RBAC decorator.

Standard FastAPI flow:

1. ``current_user`` — depends on a Bearer token, returns the live ``User``.
2. ``requires(perm)`` — returns a dependency that asserts the current user
   has the given ``"<model>:<action>"`` permission (superusers bypass).

Permissions are read from the user's groups.  Effective permissions are
``set(p.code for g in user.groups for p in g.permissions)``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.db import SessionDep
from backend.core.models import User
from backend.core.security import decode_token

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=True)

_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def current_user(
    session: SessionDep,
    token: Annotated[str, Depends(_oauth2_scheme)],
) -> User:
    """Resolve the bearer token to an active User, or raise 401."""
    try:
        payload = decode_token(token, expected_type="access")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise _credentials_error from exc

    stmt = (
        select(User)
        .where(User.id == user_id, User.deleted_at.is_(None))
        .options(selectinload(User.groups))
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise _credentials_error
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def _user_permission_codes(user: User) -> set[str]:
    return {p.code for g in user.groups for p in g.permissions}


def requires(*perms: str):
    """Build a FastAPI dependency that checks all given permission codes.

    Superusers always pass.  Use as ``Depends(requires("wms.transfer:write"))``
    or in a route's ``dependencies=[...]``.
    """

    async def _check(user: CurrentUser) -> User:
        if user.is_superuser:
            return user
        granted = _user_permission_codes(user)
        missing = [p for p in perms if p not in granted]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission(s): {', '.join(missing)}",
            )
        return user

    return _check
