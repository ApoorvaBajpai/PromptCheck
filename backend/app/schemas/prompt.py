from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PromptVersionCreate(BaseModel):
    content: str = Field(min_length=1, description="Prompt template content")
    commit_message: str | None = Field(default=None, max_length=255)
    model: str = Field(default="gemini-2.5-flash", max_length=64, description="Gemini model identifier")
    system_instruction: str | None = Field(default=None, description="System instruction prompt")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: float | None = Field(default=None, ge=0.0, le=1.0, description="Nucleus sampling probability")
    max_output_tokens: int | None = Field(default=None, gt=0, description="Maximum tokens to generate")
    response_mime_type: str | None = Field(default=None, max_length=64, description="Response MIME type (e.g. application/json)")


class PromptVersionOut(BaseModel):
    id: int
    prompt_id: int
    version_number: int
    content: str
    content_hash: str
    commit_message: str | None = None
    model: str = "gemini-2.5-flash"
    system_instruction: str | None = None
    temperature: float = 1.0
    top_p: float | None = None
    max_output_tokens: int | None = None
    response_mime_type: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    initial_content: str | None = None
    initial_version_content: str | None = None
    commit_message: str | None = None
    model: str = Field(default="gemini-2.5-flash", max_length=64)
    system_instruction: str | None = None
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    response_mime_type: str | None = None


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
    versions: list[PromptVersionOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
