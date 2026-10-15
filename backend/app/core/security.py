import base64
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from cryptography.fernet import Fernet

from app.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against the hashed password using bcrypt."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt with salt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token."""
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.now(UTC),
        "type": "access",
    }
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token."""
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") and payload.get("type") != "access":
        raise ValueError("Invalid token type: expected access token")
    return payload


def create_stream_token(user_id: int, run_id: int, expires_seconds: int = 60) -> str:
    """
    Create a short-lived (e.g. 60-second), scoped token specifically for SSE event streaming.
    Prevents long-lived bearer tokens from being exposed in URLs or query strings.
    """
    expire = datetime.now(UTC) + timedelta(seconds=expires_seconds)
    to_encode = {
        "sub": str(user_id),
        "run_id": run_id,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "stream",
    }
    return jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_stream_token(token: str) -> dict[str, Any]:
    """Decode and validate a short-lived SSE stream token."""
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != "stream":
        raise ValueError("Invalid token type: expected stream token")
    return payload


def _get_fernet() -> Fernet:
    """
    Instantiate Fernet cipher using configured encryption key.
    Fails fast with explicit error if key is missing or invalid.
    Never silently derives replacement key.
    """
    if not settings.encryption_key:
        raise ValueError("ENCRYPTION_KEY is not configured")
    try:
        raw_key = settings.encryption_key.encode("utf-8")
        # Validate format
        decoded = base64.urlsafe_b64decode(raw_key)
        if len(decoded) != 32:
            raise ValueError(f"Fernet key must decode to 32 bytes, got {len(decoded)}")
        return Fernet(raw_key)
    except Exception as exc:
        raise ValueError(
            f"Invalid ENCRYPTION_KEY: failed to initialize Fernet cipher ({exc})"
        ) from exc


def encrypt_api_key(plain_key: str) -> str:
    """Encrypt a Gemini API key at rest using Fernet symmetric encryption."""
    if not plain_key:
        return ""
    f = _get_fernet()
    return f.encrypt(plain_key.encode("utf-8")).decode("utf-8")


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an encrypted Gemini API key."""
    if not encrypted_key:
        return ""
    f = _get_fernet()
    return f.decrypt(encrypted_key.encode("utf-8")).decode("utf-8")


def mask_api_key(api_key: str) -> str:
    """Mask an API key for safe public representation (e.g. AIzaSy...****)."""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:6]}...{api_key[-4:]}"
