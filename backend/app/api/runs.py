import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_user_project
from app.database import get_db
from app.engine.events import broadcaster
from app.engine.regression import apply_regression_analysis_to_run
from app.engine.runner import run_engine_executor
from app.models.project import Project
from app.models.prompt import PromptVersion
from app.models.run import Run, RunResult
from app.models.test_case import TestCase
from app.models.user import User
from app.schemas.run import (
    BaselineSetRequest,
    RunCreate,
    RunDetailOut,
    RunOut,
    RunResultOut,
)

router = APIRouter(tags=["Runs"])

MAX_TEST_CASES_PER_RUN = 200
MAX_DAILY_RUNS_PER_PROJECT = 500


def _check_run_ownership(run_id: int, current_user: User, db: Session) -> Run:
    """Helper to verify current user owns the project associated with the run."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    project = db.query(Project).filter(Project.id == run.project_id).first()
    if not project or project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not own this project",
        )
    return run


@router.post(
    "/api/projects/{project_id}/runs",
    response_model=RunOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_run_for_project(
    project_id: int,
    payload: RunCreate,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
    auto_execute: bool = Query(True, description="Immediately queue and execute run"),
):
    """Create a new evaluation run for a prompt version and active test cases."""
    # 1. Verify prompt version exists under project
    prompt_version = (
        db.query(PromptVersion)
        .join(PromptVersion.prompt)
        .filter(
            PromptVersion.id == payload.prompt_version_id,
            PromptVersion.prompt.has(project_id=project.id),
        )
        .first()
    )
    if not prompt_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt version does not belong to this project",
        )

    # 2. Check Daily Quota Caps (Requirement 19)
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_runs_count = (
        db.query(Run).filter(Run.project_id == project.id, Run.created_at >= today_start).count()
    )
    if today_runs_count >= MAX_DAILY_RUNS_PER_PROJECT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily run quota exceeded ({MAX_DAILY_RUNS_PER_PROJECT} runs per day)",
        )

    # 3. Check test case count cap (Requirement 19)
    test_count = (
        db.query(TestCase)
        .filter(TestCase.project_id == project.id, TestCase.is_active == True)  # noqa: E712
        .count()
    )
    if test_count > MAX_TEST_CASES_PER_RUN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Test case count ({test_count}) exceeds max limit per run "
                f"({MAX_TEST_CASES_PER_RUN})"
            ),
        )

    # 4. Check explicit baseline if supplied
    baseline_id = payload.baseline_run_id
    if baseline_id is not None:
        base_run = (
            db.query(Run)
            .filter(Run.id == baseline_id, Run.project_id == project.id)
            .first()
        )
        if not base_run or base_run.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Specified baseline run #{baseline_id} does not exist or is not completed.",
            )

    run = Run(
        project_id=project.id,
        prompt_version_id=prompt_version.id,
        baseline_run_id=baseline_id,
        status="queued",
        total_tests=test_count,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Trigger async execution if auto_execute is True
    if auto_execute:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                run_engine_executor(run_id=run.id, enable_cache=payload.enable_cache)
            )
        except RuntimeError:
            asyncio.create_task(
                run_engine_executor(run_id=run.id, enable_cache=payload.enable_cache)
            )

    return RunOut.model_validate(run)


@router.get("/api/projects/{project_id}/runs", response_model=list[RunOut])
def list_project_runs(
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """List all evaluation runs for a project."""
    runs = db.query(Run).filter(Run.project_id == project.id).order_by(Run.created_at.desc()).all()
    return [RunOut.model_validate(r) for r in runs]


@router.get("/api/runs/{run_id}", response_model=RunDetailOut)
def get_run_details(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get status, summary metrics, and test case results for a run."""
    run = _check_run_ownership(run_id, current_user, db)
    results = (
        db.query(RunResult).filter(RunResult.run_id == run.id).order_by(RunResult.id.asc()).all()
    )
    return RunDetailOut(
        id=run.id,
        project_id=run.project_id,
        prompt_version_id=run.prompt_version_id,
        baseline_run_id=run.baseline_run_id,
        status=run.status,
        total_tests=run.total_tests,
        passed_tests=run.passed_tests,
        failed_tests=run.failed_tests,
        error_message=run.error_message,
        summary=run.summary,
        heartbeat_at=run.heartbeat_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
        results=[RunResultOut.model_validate(r) for r in results],
    )


@router.post("/runs/{run_id}/baseline", response_model=RunDetailOut)
@router.post("/api/runs/{run_id}/baseline", response_model=RunDetailOut)
def set_run_baseline(
    run_id: int,
    payload: BaselineSetRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Designate a run as baseline or configure explicit baseline comparison (Requirement 12).
    """
    run = _check_run_ownership(run_id, current_user, db)
    project = db.query(Project).filter(Project.id == run.project_id).first()

    target_baseline_id = payload.baseline_run_id if payload else None

    if target_baseline_id is not None:
        # Validate target baseline
        base_run = (
            db.query(Run)
            .filter(
                Run.id == target_baseline_id,
                Run.project_id == run.project_id,
                Run.id != run.id,
            )
            .first()
        )
        if not base_run or base_run.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Specified baseline run #{target_baseline_id} does not exist or is not completed.",
            )

        run.baseline_run_id = target_baseline_id
        if payload and payload.set_as_project_baseline and project:
            project.baseline_run_id = target_baseline_id
        db.commit()

        # Re-compute regression analysis against selected baseline
        apply_regression_analysis_to_run(db, run.id, explicit_baseline_id=target_baseline_id)
    else:
        # If no explicit baseline_run_id is passed, designate this run as the project's baseline
        if run.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only completed runs can be designated as a project baseline.",
            )
        if project:
            project.baseline_run_id = run.id
            db.commit()

        # Re-evaluate this run's regressions if applicable
        if run.status == "completed":
            apply_regression_analysis_to_run(db, run.id)

    db.refresh(run)
    results = (
        db.query(RunResult).filter(RunResult.run_id == run.id).order_by(RunResult.id.asc()).all()
    )
    return RunDetailOut(
        id=run.id,
        project_id=run.project_id,
        prompt_version_id=run.prompt_version_id,
        baseline_run_id=run.baseline_run_id,
        status=run.status,
        total_tests=run.total_tests,
        passed_tests=run.passed_tests,
        failed_tests=run.failed_tests,
        error_message=run.error_message,
        summary=run.summary,
        heartbeat_at=run.heartbeat_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
        results=[RunResultOut.model_validate(r) for r in results],
    )


@router.get("/api/runs/{run_id}/results", response_model=list[RunResultOut])
def list_run_results(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List test results for a specific run."""
    run = _check_run_ownership(run_id, current_user, db)
    results = (
        db.query(RunResult).filter(RunResult.run_id == run.id).order_by(RunResult.id.asc()).all()
    )
    return [RunResultOut.model_validate(r) for r in results]


@router.post("/api/runs/{run_id}/cancel", response_model=RunOut)
async def cancel_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel an active or queued run (Requirement 14)."""
    run = _check_run_ownership(run_id, current_user, db)
    if run.status in ("completed", "failed", "cancelled"):
        return RunOut.model_validate(run)

    run.status = "cancelled"
    run.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(run)

    # Mark remaining pending results as cancelled
    pending_results = (
        db.query(RunResult).filter(RunResult.run_id == run.id, RunResult.status == "pending").all()
    )
    for pr in pending_results:
        pr.status = "cancelled"
        pr.error_message = "Cancelled by user"
    db.commit()

    await broadcaster.emit(
        run.id,
        "run_cancelled",
        {"run_id": run.id, "status": "cancelled"},
    )

    return RunOut.model_validate(run)


@router.get("/api/runs/{run_id}/stream")
async def stream_run_events(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Stream evaluation progress via Server-Sent Events (SSE) (Requirement 16).
    """
    _check_run_ownership(run_id, current_user, db)

    queue = await broadcaster.subscribe(run_id)

    async def event_generator():
        try:
            # Yield initial connection confirmation event
            yield broadcaster.format_sse(
                "connected", {"run_id": run_id, "time": str(datetime.now(UTC))}
            )

            while True:
                msg = await queue.get()
                event_type = msg.get("event", "message")
                data = msg.get("data", {})
                yield broadcaster.format_sse(event_type, data)

                if event_type in ("run_completed", "run_cancelled", "run_failed"):
                    break
        finally:
            await broadcaster.unsubscribe(run_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
