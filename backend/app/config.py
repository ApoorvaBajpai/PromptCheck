from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PromptCheck API"
    environment: str = "development"
    debug: bool = True
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/promptcheck"
    secret_key: str = "promptcheck-insecure-dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days
    encryption_key: str = "t8ugVmp3vGlAT11bNiEaJELvyj-1f8qZkaQTDH1Au0E="
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
