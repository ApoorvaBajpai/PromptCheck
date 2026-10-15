import base64
from typing import Self

from cryptography.fernet import Fernet
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEV_SECRET = "promptcheck-insecure-dev-secret-key-change-in-production"
INSECURE_DEV_ENCRYPTION_KEY = "t8ugVmp3vGlAT11bNiEaJELvyj-1f8qZkaQTDH1Au0E="


class Settings(BaseSettings):
    app_name: str = "PromptCheck API"
    environment: str = "development"
    debug: bool = True
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/promptcheck"
    secret_key: str = INSECURE_DEV_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60  # Default 60 min (reduced from 7 days)
    encryption_key: str = INSECURE_DEV_ENCRYPTION_KEY
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> Self:
        is_production = self.environment.lower() in ("production", "prod", "staging")

        # 1. Validate encryption key format across all environments
        if self.encryption_key:
            try:
                raw = base64.urlsafe_b64decode(self.encryption_key.encode("utf-8"))
                if len(raw) != 32:
                    raise ValueError("ENCRYPTION_KEY must decode to exactly 32 bytes")
                Fernet(self.encryption_key.encode("utf-8"))
            except Exception as exc:
                raise ValueError(
                    f"Invalid ENCRYPTION_KEY: must be a 32-byte url-safe base64 key ({exc})"
                ) from exc
        elif is_production:
            raise ValueError("ENCRYPTION_KEY is required in production")

        # 2. Strict validation in production mode
        if is_production:
            if (
                not self.secret_key
                or self.secret_key == INSECURE_DEV_SECRET
                or len(self.secret_key) < 32
            ):
                raise ValueError(
                    "SECRET_KEY must be explicitly set to a strong secret (at least 32 characters) in production"
                )
            if (
                not self.encryption_key
                or self.encryption_key == INSECURE_DEV_ENCRYPTION_KEY
            ):
                raise ValueError(
                    "ENCRYPTION_KEY must be explicitly set to a unique Fernet key in production"
                )
            if not self.database_url:
                raise ValueError("DATABASE_URL is required in production")

        return self


settings = Settings()
