from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RunCreate(BaseModel):
    prompt_version_id: int = Field(description="ID of the immutable prompt version to execute")
    enable_cache: bool = Field(
        default=True, description="Enable output caching for identical inputs"
    )
    baseline_run_id: int | None = Field(
        default=None, description="Optional explicit baseline run ID for regression analysis"
    )
    repeat_count: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Number of times each test should be executed for flakiness / stability analysis",
    )


class BaselineSetRequest(BaseModel):
    baseline_run_id: int | None = Field(
        default=None,
        description="Optional baseline run ID to compare against. If omitted, designates run as project baseline.",
    )
    set_as_project_baseline: bool = Field(
        default=True,
        description="Whether to designate this run (or the selected baseline) as project baseline",
    )


class RunResultOut(BaseModel):
    id: int
    run_id: int
    test_case_id: int
    repeat_index: int = 0
    status: str
    rendered_prompt: str | None = None
    output: str | None = None
    error_message: str | None = None
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cached: bool
    score: float | None = None
    classification: str | None = None
    comparison_details: dict[str, Any] | None = None
    assertion_results: list[dict[str, Any]]
    retry_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunOut(BaseModel):
    id: int
    project_id: int
    prompt_version_id: int
    baseline_run_id: int | None = None
    repeat_count: int = 1
    status: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    error_message: str | None = None
    summary: dict[str, Any] | None = None
    heartbeat_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunDetailOut(RunOut):
    results: list[RunResultOut] = Field(default_factory=list)
