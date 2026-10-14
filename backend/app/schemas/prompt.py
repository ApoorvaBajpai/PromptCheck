from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PromptVersionCreate(BaseModel):
    content: str = Field(min_length=1, description="Prompt template content")
    commit_message: str | None = Field(default=None, max_length=255)


class PromptVersionOut(BaseModel):
    id: int
    prompt_id: int
    version_number: int
    content: str
    content_hash: str
    commit_message: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    initial_content: str | None = None


class PromptUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class PromptOut(BaseModel):
    id: int
    project_id: int
    name: str
    description: str | None = None
    versions_count: int = 0
    latest_version: PromptVersionOut | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
