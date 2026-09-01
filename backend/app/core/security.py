"""Password hashing and JWT utilities."""
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

BCRYPT_ROUNDS = 12
BCRYPT_MAX_PASSWORD_BYTES = 72

# ── Password ──────────────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plain-text password."""
    password_bytes = plain.encode("utf-8")[:BCRYPT_MAX_PASSWORD_BYTES]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    password_bytes = plain.encode("utf-8")[:BCRYPT_MAX_PASSWORD_BYTES]
    try:
        return bcrypt.checkpw(password_bytes, hashed.encode("utf-8"))
    except ValueError:
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────

ACCESS_TOKEN_EXPIRE_MINUTES = 15


def create_access_token(
    user_id: str,
    org_id: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed HS256 JWT access token."""
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": user_id,
        "org_id": org_id,
        "role": role,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Raises jwt.PyJWTError on invalid/expired tokens (caller converts to HTTP 401).
    """
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


# ── Refresh / invite tokens ───────────────────────────────────────────────────

REFRESH_TOKEN_BYTES = 64
INVITE_TOKEN_BYTES = 32


def generate_refresh_token() -> str:
    """Generate a cryptographically secure opaque refresh token."""
    return secrets.token_hex(REFRESH_TOKEN_BYTES)


def generate_invite_token() -> str:
    """Generate a cryptographically secure invite token."""
    return secrets.token_hex(INVITE_TOKEN_BYTES)
