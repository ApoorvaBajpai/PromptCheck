from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RunCreate(BaseModel):
    prompt_version_id: int = Field(description="ID of the immutable prompt version to execute")
    enable_cache: bool = Field(
        default=True, description="Enable output caching for identical inputs"
    )


class RunResultOut(BaseModel):
    id: int
    run_id: int
    test_case_id: int
    status: str
    rendered_prompt: str | None = None
    output: str | None = None
    error_message: str | None = None
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cached: bool
    assertion_results: list[dict[str, Any]]
    retry_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunOut(BaseModel):
    id: int
    project_id: int
    prompt_version_id: int
    status: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    error_message: str | None = None
    heartbeat_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunDetailOut(RunOut):
    results: list[RunResultOut] = Field(default_factory=list)
