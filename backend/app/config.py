from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PromptCheck API"
    environment: str = "development"
    debug: bool = True
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/promptcheck"
    secret_key: str = "promptcheck-insecure-dev-secret-key-change-in-production"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
