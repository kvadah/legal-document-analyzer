"""FastAPI dependency functions for auth and RBAC."""
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    """Decoded JWT claims, injected as a dependency into route handlers."""

    id: str
    org_id: str
    role: str


def _extract_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
) -> str:
    """Extract raw JWT from Authorization header or cookie."""
    if credentials is not None:
        return credentials.credentials
    if access_token is not None:
        return access_token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "unauthorized", "message": "Missing authentication token"},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Annotated[str, Depends(_extract_token)],
) -> CurrentUser:
    """Parse JWT and return the current authenticated user.

    Raises HTTP 401 if the token is missing, invalid, or expired.
    """
    try:
        claims = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "token_expired", "message": "Access token has expired"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid authentication token"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentUser(
        id=claims["sub"],
        org_id=claims["org_id"],
        role=claims["role"],
    )


def require_role(*roles: str):
    """Return a FastAPI dependency that enforces one of the given roles.

    Usage::

        @router.post("/invite", dependencies=[Depends(require_role("admin"))])
    """

    def _check_role(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "forbidden",
                    "message": f"Requires one of roles: {', '.join(roles)}",
                },
            )
        return current_user

    return _check_role
