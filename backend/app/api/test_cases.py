import csv
import io
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_user_project, get_user_test_case
from app.database import get_db
from app.models.project import Project
from app.models.test_case import TestCase
from app.schemas.test_case import (
    TestCaseCreate,
    TestCaseOut,
    TestCaseUpdate,
    TestImportResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}/tests", tags=["Test Cases"])

MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_IMPORT_ROWS = 500
MAX_TESTS_PER_PROJECT = 1000


def sanitize_formula_injection(text: str) -> str:
    """Protect against CSV formula injection attacks by escaping leading command characters."""
    if text and text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


@router.post("", response_model=TestCaseOut, status_code=status.HTTP_201_CREATED)
def create_test_case(
    payload: TestCaseCreate,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """Create a new test case under the project."""
    current_count = db.query(TestCase).filter(TestCase.project_id == project.id).count()
    if current_count >= MAX_TESTS_PER_PROJECT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project test case limit ({MAX_TESTS_PER_PROJECT}) reached",
        )

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
    """Import test cases via JSON batch payload with strict schema and limits validation."""
    body = await request.json()
    if isinstance(body, list):
        items_raw = body
    elif isinstance(body, dict):
        items_raw = body.get("tests", [])
    else:
        items_raw = []

    if len(items_raw) > MAX_IMPORT_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import exceeds maximum allowed rows ({MAX_IMPORT_ROWS})",
        )

    current_count = db.query(TestCase).filter(TestCase.project_id == project.id).count()
    if current_count + len(items_raw) > MAX_TESTS_PER_PROJECT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import would exceed project test case limit ({MAX_TESTS_PER_PROJECT})",
        )

    validation_errors = []
    validated_cases = []

    for idx, item in enumerate(items_raw):
        if not isinstance(item, dict):
            validation_errors.append(f"Row {idx + 1}: expected JSON object")
            continue

        try:
            name = item.get("name", f"Imported Test {idx + 1}")
            inputs = item.get("inputs", {})
            expected_output = item.get("expected_output")
            assertions = item.get("assertions", [])

            validated = TestCaseCreate(
                name=name,
                inputs=inputs if isinstance(inputs, dict) else {"input": str(inputs)},
                expected_output=expected_output,
                assertions=assertions if isinstance(assertions, list) else [],
            )
            validated_cases.append(validated)
        except ValidationError as ve:
            validation_errors.append(f"Row {idx + 1}: {ve.errors()[0]['msg']}")

    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Import validation failed", "errors": validation_errors[:20]},
        )

    created_items: list[TestCase] = []
    for val in validated_cases:
        tc = TestCase(
            project_id=project.id,
            name=val.name,
            inputs=val.inputs,
            expected_output=val.expected_output,
            assertions=val.assertions,
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
    """Import test cases via uploaded CSV or JSON file with row-level validation and formula injection defenses."""
    content_bytes = await file.read()
    if len(content_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload file exceeds maximum limit of {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB",
        )

    filename = file.filename or ""
    validation_errors = []
    validated_cases = []

    if filename.endswith(".json") or file.content_type == "application/json":
        try:
            data = json.loads(content_bytes.decode("utf-8"))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON file: {e}",
            )

        items_list = data if isinstance(data, list) else data.get("tests", [])
        if len(items_list) > MAX_IMPORT_ROWS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File contains {len(items_list)} rows, exceeding max limit ({MAX_IMPORT_ROWS})",
            )

        for idx, item in enumerate(items_list):
            if not isinstance(item, dict):
                validation_errors.append(f"Row {idx + 1}: expected object")
                continue
            try:
                name = item.get("name", f"Imported Test {idx + 1}")
                inputs = item.get("inputs") or item.get("input_variables") or {}
                expected_output = item.get("expected_output")
                assertions = item.get("assertions") or []

                validated = TestCaseCreate(
                    name=name,
                    inputs=inputs if isinstance(inputs, dict) else {"input": str(inputs)},
                    expected_output=expected_output,
                    assertions=assertions if isinstance(assertions, list) else [],
                )
                validated_cases.append(validated)
            except ValidationError as ve:
                validation_errors.append(f"Row {idx + 1}: {ve.errors()[0]['msg']}")

    else:
        # CSV parsing with formula injection defense
        try:
            csv_text = content_bytes.decode("utf-8-sig")
            reader = list(csv.DictReader(io.StringIO(csv_text)))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse CSV file: {e}",
            )

        if len(reader) > MAX_IMPORT_ROWS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CSV contains {len(reader)} rows, exceeding max limit ({MAX_IMPORT_ROWS})",
            )

        for idx, row in enumerate(reader):
            name = sanitize_formula_injection(row.get("name") or row.get("test_name") or f"Imported CSV Test {idx + 1}")
            raw_input = row.get("inputs") or row.get("input") or "{}"
            try:
                inputs_val: Any = json.loads(raw_input)
                if not isinstance(inputs_val, dict):
                    inputs_val = {"input": sanitize_formula_injection(str(inputs_val))}
            except Exception:
                inputs_val = {"input": sanitize_formula_injection(str(raw_input))}

            raw_assertions = row.get("assertions") or "[]"
            try:
                assertions_val: Any = json.loads(raw_assertions)
                if not isinstance(assertions_val, list):
                    assertions_val = []
            except Exception:
                assertions_val = (
                    [{"type": "contains", "value": raw_assertions}] if raw_assertions else []
                )

            expected_output = row.get("expected_output")
            if expected_output:
                expected_output = sanitize_formula_injection(str(expected_output))

            try:
                validated = TestCaseCreate(
                    name=name,
                    inputs=inputs_val,
                    expected_output=expected_output,
                    assertions=assertions_val,
                )
                validated_cases.append(validated)
            except ValidationError as ve:
                validation_errors.append(f"Row {idx + 1}: {ve.errors()[0]['msg']}")

    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "File import validation failed", "errors": validation_errors[:20]},
        )

    current_count = db.query(TestCase).filter(TestCase.project_id == project.id).count()
    if current_count + len(validated_cases) > MAX_TESTS_PER_PROJECT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import would exceed project test case limit ({MAX_TESTS_PER_PROJECT})",
        )

    created_items: list[TestCase] = []
    for val in validated_cases:
        tc = TestCase(
            project_id=project.id,
            name=val.name,
            inputs=val.inputs,
            expected_output=val.expected_output,
            assertions=val.assertions,
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
    payload: TestCaseUpdate,
    test_case: TestCase = Depends(get_user_test_case),
    db: Session = Depends(get_db),
):
    """Update a test case directly by test ID with ownership validation."""
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


@standalone_tests_router.delete("/api/test-cases/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
@standalone_tests_router.delete("/api/tests/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_standalone_test_case(
    test_case: TestCase = Depends(get_user_test_case),
    db: Session = Depends(get_db),
):
    """Soft delete a test case directly by test ID with ownership validation."""
    test_case.is_active = False
    test_case.deleted_at = datetime.now(UTC)
    db.commit()
    return None


@standalone_tests_router.post(
    "/api/test-cases/{test_id}/reactivate", response_model=TestCaseOut
)
@standalone_tests_router.post(
    "/api/tests/{test_id}/reactivate", response_model=TestCaseOut
)
def reactivate_standalone_test_case(
    test_case: TestCase = Depends(get_user_test_case),
    db: Session = Depends(get_db),
):
    """Reactivate a soft-deleted test case."""
    test_case.is_active = True
    test_case.deleted_at = None
    db.commit()
    db.refresh(test_case)
    return TestCaseOut.model_validate(test_case)
