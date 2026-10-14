import csv
import io
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_user_project
from app.database import get_db
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.user import User
from app.schemas.test_case import (
    TestCaseBatchImport,
    TestCaseCreate,
    TestCaseOut,
    TestCaseUpdate,
    TestImportResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}/tests", tags=["Test Cases"])


@router.post("", response_model=TestCaseOut, status_code=status.HTTP_201_CREATED)
def create_test_case(
    payload: TestCaseCreate,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """Create a new test case under the project."""
    test_case = TestCase(
        project_id=project.id,
        name=payload.name,
        inputs=payload.inputs,
        expected_output=payload.expected_output,
        assertions=payload.assertions,
        is_active=True,
    )
    db.add(test_case)
    db.commit()
    db.refresh(test_case)
    return TestCaseOut.model_validate(test_case)


@router.get("", response_model=list[TestCaseOut])
def list_test_cases(
    include_inactive: bool = Query(
        False,
        description="Include soft-deleted/deactivated tests",
    ),
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """List test cases for the project. By default only active tests are returned."""
    query = db.query(TestCase).filter(TestCase.project_id == project.id)
    if not include_inactive:
        query = query.filter(TestCase.is_active == True)  # noqa: E712
    test_cases = query.order_by(TestCase.id.asc()).all()
    return [TestCaseOut.model_validate(t) for t in test_cases]


@router.get("/{test_id}", response_model=TestCaseOut)
def get_test_case(
    test_id: int,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """Get single test case by ID."""
    test_case = (
        db.query(TestCase).filter(TestCase.id == test_id, TestCase.project_id == project.id).first()
    )
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found",
        )
    return TestCaseOut.model_validate(test_case)


@router.put("/{test_id}", response_model=TestCaseOut)
def update_test_case(
    test_id: int,
    payload: TestCaseUpdate,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """Update test case details or reactivate."""
    test_case = (
        db.query(TestCase).filter(TestCase.id == test_id, TestCase.project_id == project.id).first()
    )
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found",
        )

    if payload.name is not None:
        test_case.name = payload.name
    if payload.inputs is not None:
        test_case.inputs = payload.inputs
    if payload.expected_output is not None:
        test_case.expected_output = payload.expected_output
    if payload.assertions is not None:
        test_case.assertions = payload.assertions
    if payload.is_active is not None:
        test_case.is_active = payload.is_active
        if payload.is_active:
            test_case.deleted_at = None
        else:
            test_case.deleted_at = datetime.now(UTC)

    db.commit()
    db.refresh(test_case)
    return TestCaseOut.model_validate(test_case)


@router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_case(
    test_id: int,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """
    Soft delete a test case (Invariant 3).
    Marks is_active=False and records deleted_at timestamp.
    """
    test_case = (
        db.query(TestCase).filter(TestCase.id == test_id, TestCase.project_id == project.id).first()
    )
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found",
        )

    test_case.is_active = False
    test_case.deleted_at = datetime.now(UTC)
    db.commit()
    return None


@router.post("/import", response_model=TestImportResponse, status_code=status.HTTP_201_CREATED)
@router.post("/batch", response_model=TestImportResponse, status_code=status.HTTP_201_CREATED)
async def import_test_cases_json(
    request: Request,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """Import test cases via JSON batch payload. Supports either {'tests': [...]} or [...]"""
    body = await request.json()
    if isinstance(body, list):
        items_raw = body
    elif isinstance(body, dict):
        items_raw = body.get("tests", [])
    else:
        items_raw = []

    created_items: list[TestCase] = []
    for item in items_raw:
        if isinstance(item, dict):
            name = item.get("name", "Imported Test")
            inputs = item.get("inputs", {})
            expected_output = item.get("expected_output")
            assertions = item.get("assertions", [])
        else:
            name = getattr(item, "name", "Imported Test")
            inputs = getattr(item, "inputs", {})
            expected_output = getattr(item, "expected_output", None)
            assertions = getattr(item, "assertions", [])

        tc = TestCase(
            project_id=project.id,
            name=name,
            inputs=inputs,
            expected_output=expected_output,
            assertions=assertions,
            is_active=True,
        )
        db.add(tc)
        created_items.append(tc)

    db.commit()
    for tc in created_items:
        db.refresh(tc)

    return TestImportResponse(
        imported_count=len(created_items),
        test_cases=[TestCaseOut.model_validate(t) for t in created_items],
    )


@router.post("/import-file", response_model=TestImportResponse, status_code=status.HTTP_201_CREATED)
@router.post("/import/file", response_model=TestImportResponse, status_code=status.HTTP_201_CREATED)
@router.post("/import/csv", response_model=TestImportResponse, status_code=status.HTTP_201_CREATED)
async def import_test_cases_file(
    file: UploadFile = File(...),
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """Import test cases via uploaded CSV or JSON file."""
    content_bytes = await file.read()
    filename = file.filename or ""

    created_items: list[TestCase] = []

    if filename.endswith(".json") or file.content_type == "application/json":
        try:
            data = json.loads(content_bytes.decode("utf-8"))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON file: {e}",
            )

        items_list = data if isinstance(data, list) else data.get("tests", [])
        for item in items_list:
            name = item.get("name", "Imported Test")
            inputs = item.get("inputs") or item.get("input_variables") or {}
            expected_output = item.get("expected_output")
            assertions = item.get("assertions") or []
            tc = TestCase(
                project_id=project.id,
                name=name,
                inputs=inputs if isinstance(inputs, dict) else {"input": str(inputs)},
                expected_output=expected_output,
                assertions=assertions if isinstance(assertions, list) else [],
                is_active=True,
            )
            db.add(tc)
            created_items.append(tc)

    else:
        # CSV parsing
        try:
            csv_text = content_bytes.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(csv_text))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse CSV file: {e}",
            )

        for row in reader:
            name = row.get("name") or row.get("test_name") or "Imported CSV Test"
            raw_input = row.get("inputs") or row.get("input") or "{}"
            try:
                inputs_val: Any = json.loads(raw_input)
                if not isinstance(inputs_val, dict):
                    inputs_val = {"input": inputs_val}
            except Exception:
                inputs_val = {"input": raw_input}

            raw_assertions = row.get("assertions") or "[]"
            try:
                assertions_val: Any = json.loads(raw_assertions)
                if not isinstance(assertions_val, list):
                    assertions_val = []
            except Exception:
                assertions_val = (
                    [{"type": "contains", "value": raw_assertions}] if raw_assertions else []
                )

            tc = TestCase(
                project_id=project.id,
                name=name,
                inputs=inputs_val,
                expected_output=row.get("expected_output"),
                assertions=assertions_val,
                is_active=True,
            )
            db.add(tc)
            created_items.append(tc)

    db.commit()
    for tc in created_items:
        db.refresh(tc)

    return TestImportResponse(
        imported_count=len(created_items),
        test_cases=[TestCaseOut.model_validate(t) for t in created_items],
    )


# --- Standalone Test Routes (/api/test-cases/... and /api/tests/...) ---
standalone_tests_router = APIRouter(tags=["Test Cases"])


@standalone_tests_router.put("/api/test-cases/{test_id}", response_model=TestCaseOut)
@standalone_tests_router.put("/api/tests/{test_id}", response_model=TestCaseOut)
def update_standalone_test_case(
    test_id: int,
    payload: TestCaseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a test case directly by test ID with ownership validation."""
    test_case = db.query(TestCase).filter(TestCase.id == test_id).first()
    if not test_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found")
    project = db.query(Project).filter(Project.id == test_case.project_id).first()
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found")

    if payload.name is not None:
        test_case.name = payload.name
    if payload.inputs is not None:
        test_case.inputs = payload.inputs
    if payload.expected_output is not None:
        test_case.expected_output = payload.expected_output
    if payload.assertions is not None:
        test_case.assertions = payload.assertions
    if payload.is_active is not None:
        test_case.is_active = payload.is_active
        if payload.is_active:
            test_case.deleted_at = None
        else:
            test_case.deleted_at = datetime.now(UTC)

    db.commit()
    db.refresh(test_case)
    return TestCaseOut.model_validate(test_case)


@standalone_tests_router.delete(
    "/api/test-cases/{test_id}", status_code=status.HTTP_204_NO_CONTENT
)
@standalone_tests_router.delete("/api/tests/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_standalone_test_case(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft delete a test case directly by test ID."""
    test_case = db.query(TestCase).filter(TestCase.id == test_id).first()
    if not test_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found")
    project = db.query(Project).filter(Project.id == test_case.project_id).first()
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found")

    test_case.is_active = False
    test_case.deleted_at = datetime.now(UTC)
    db.commit()
    return None


@standalone_tests_router.post(
    "/api/test-cases/{test_id}/reactivate", response_model=TestCaseOut
)
@standalone_tests_router.post("/api/tests/{test_id}/reactivate", response_model=TestCaseOut)
def reactivate_standalone_test_case(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reactivate a soft-deleted test case directly by test ID."""
    test_case = db.query(TestCase).filter(TestCase.id == test_id).first()
    if not test_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found")
    project = db.query(Project).filter(Project.id == test_case.project_id).first()
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found")

    test_case.is_active = True
    test_case.deleted_at = None
    db.commit()
    db.refresh(test_case)
    return TestCaseOut.model_validate(test_case)
