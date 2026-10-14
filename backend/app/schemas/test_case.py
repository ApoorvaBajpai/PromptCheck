from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TestCaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected_output: str | None = None
    assertions: list[dict[str, Any]] = Field(default_factory=list)


class TestCaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    inputs: dict[str, Any] | None = None
    expected_output: str | None = None
    assertions: list[dict[str, Any]] | None = None
    is_active: bool | None = None


class TestCaseOut(BaseModel):
    id: int
    project_id: int
    name: str
    inputs: dict[str, Any]
    expected_output: str | None = None
    assertions: list[dict[str, Any]]
    is_active: bool
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestCaseBatchImport(BaseModel):
    tests: list[TestCaseCreate]


class TestImportResponse(BaseModel):
    imported_count: int
    test_cases: list[TestCaseOut]
