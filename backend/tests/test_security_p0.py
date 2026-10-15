import base64

import jwt
import pytest
from cryptography.fernet import Fernet

from app.config import INSECURE_DEV_ENCRYPTION_KEY, INSECURE_DEV_SECRET, Settings
from app.core import security


def test_encryption_decryption_roundtrip():
    """Verify Fernet encryption and decryption works correctly for valid keys."""
    raw_api_key = "AIzaSyTestSecretApiKeyForGemini12345"
    encrypted = security.encrypt_api_key(raw_api_key)
    assert encrypted != raw_api_key
    assert len(encrypted) > 20

    decrypted = security.decrypt_api_key(encrypted)
    assert decrypted == raw_api_key


def test_empty_api_key_handling():
    """Verify empty or None API keys encrypt/decrypt to empty string without raising."""
    assert security.encrypt_api_key("") == ""
    assert security.decrypt_api_key("") == ""


def test_mask_api_key():
    """Verify API key masking never reveals full plaintext."""
    key = "AIzaSyD-1234567890abcdefghijklmnop"
    masked = security.mask_api_key(key)
    assert masked.startswith("AIzaSy")
    assert masked.endswith("mnop")
    assert "..." in masked
    assert "1234567890abcdef" not in masked

    short_key = "12345"
    assert security.mask_api_key(short_key) == "****"


def test_jwt_create_and_verify():
    """Verify JWT access token creation and decoding."""
    user_id = 42
    token = security.create_access_token(user_id)
    assert token and isinstance(token, str)

    payload = security.decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_jwt_wrong_secret_rejection():
    """Verify JWT signed with a different secret is rejected."""
    token = security.create_access_token(99)
    # Attempt decoding with wrong secret
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "wrong-secret-key-that-does-not-match", algorithms=["HS256"])


def test_stream_token_lifecycle():
    """Verify short-lived SSE stream token creation and scoped verification."""
    token = security.create_stream_token(user_id=10, run_id=5, expires_seconds=30)
    payload = security.decode_stream_token(token)
    assert payload["sub"] == "10"
    assert payload["run_id"] == 5
    assert payload["type"] == "stream"

    # Stream token cannot be used as an access token
    with pytest.raises(ValueError, match="Invalid token type"):
        security.decode_access_token(token)


def test_production_fails_fast_on_missing_secret():
    """In production mode, missing or default SECRET_KEY must raise ValueError."""
    with pytest.raises(ValueError, match="SECRET_KEY must be explicitly set"):
        Settings(
            environment="production",
            secret_key=INSECURE_DEV_SECRET,
            encryption_key=Fernet.generate_key().decode(),
            database_url="postgresql+psycopg2://postgres:postgres@localhost:5432/test",
        )


def test_production_fails_fast_on_default_encryption_key():
    """In production mode, default ENCRYPTION_KEY must raise ValueError."""
    with pytest.raises(ValueError, match="ENCRYPTION_KEY must be explicitly set to a unique Fernet key"):
        Settings(
            environment="production",
            secret_key="a" * 32,
            encryption_key=INSECURE_DEV_ENCRYPTION_KEY,
            database_url="postgresql+psycopg2://postgres:postgres@localhost:5432/test",
        )


def test_malformed_encryption_key_rejected():
    """Any environment must fail fast if ENCRYPTION_KEY is not a valid 32-byte Fernet key."""
    # Too short
    with pytest.raises(ValueError, match="Invalid ENCRYPTION_KEY"):
        Settings(
            environment="development",
            encryption_key="not-base64-and-not-32-bytes",
        )

    # Valid base64 but wrong byte length (16 bytes instead of 32)
    short_b64 = base64.urlsafe_b64encode(b"0123456789abcdef").decode()
    with pytest.raises(ValueError, match="Invalid ENCRYPTION_KEY"):
        Settings(
            environment="development",
            encryption_key=short_b64,
        )


def test_security_does_not_silently_fallback():
    """If encryption_key is invalid or broken, _get_fernet must raise an error, NOT silently fallback."""
    # Temporarily corrupt settings encryption key
    original = security.settings.encryption_key
    try:
        security.settings.encryption_key = "invalid-key"
        with pytest.raises(ValueError, match="Invalid ENCRYPTION_KEY"):
            security._get_fernet()
    finally:
        security.settings.encryption_key = original
