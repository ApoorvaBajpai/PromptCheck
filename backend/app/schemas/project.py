from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    gemini_api_key: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class ProjectApiKeyIn(BaseModel):
    api_key: str = Field(
        min_length=1, description="Plaintext Gemini API key to be encrypted at rest"
    )


class ProjectApiKeyOut(BaseModel):
    has_key: bool
    masked_key: str | None = None


class ProjectOut(BaseModel):
    id: int
    user_id: int
    name: str
    description: str | None = None
    has_api_key: bool = False
    masked_api_key: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
