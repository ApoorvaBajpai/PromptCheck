import asyncio
import hashlib
from datetime import UTC, datetime
from typing import Any

from app.core.security import decrypt_api_key
from app.database import SessionLocal
from app.engine.assertions import evaluate_assertions
from app.engine.client import (
    BaseGeminiClient,
    GeminiAuthError,
    GeminiClient,
    GeminiRateLimitError,
    GeminiServerError,
)
from app.engine.events import broadcaster
from app.engine.prompt_renderer import PromptRenderError, render_prompt
from app.engine.rate_limiter import RateLimiter, calculate_backoff
from app.models.project import Project
from app.models.prompt import PromptVersion
from app.models.run import OutputCache, Run, RunResult
from app.models.test_case import TestCase


def _compute_cache_key(model: str, rendered_prompt: str) -> str:
    """Compute deterministic SHA-256 cache key for output caching."""
    content = f"{model}:{rendered_prompt}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def execute_test_case(
    run_id: int,
    test_case_id: int,
    prompt_template: str,
    test_name: str,
    inputs: dict[str, Any],
    assertions: list[dict[str, Any]],
    client: BaseGeminiClient,
    rate_limiter: RateLimiter,
    semaphore: asyncio.Semaphore,
    model: str = "gemini-2.5-flash",
    enable_cache: bool = True,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Execute a single test case with bounded concurrency, caching, rate limiting, and backoff."""
    async with semaphore:
        # Check cancellation state before running
        with SessionLocal() as db:
            current_run = db.query(Run).filter(Run.id == run_id).first()
            if current_run and current_run.status == "cancelled":
                return {
                    "test_case_id": test_case_id,
                    "status": "cancelled",
                    "rendered_prompt": "",
                    "output": None,
                    "error_message": "Run was cancelled by user",
                    "latency_ms": 0.0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cached": False,
                    "assertion_results": [],
                    "retry_count": 0,
                }

        # 1. Render prompt with Jinja2 sandbox
        try:
            rendered = render_prompt(prompt_template, inputs)
        except PromptRenderError as exc:
            return {
                "test_case_id": test_case_id,
                "status": "error",
                "rendered_prompt": None,
                "output": None,
                "error_message": f"Prompt rendering error: {exc}",
                "latency_ms": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cached": False,
                "assertion_results": [],
                "retry_count": 0,
            }

        # 2. Output Cache Check
        cache_key = _compute_cache_key(model, rendered)
        if enable_cache:
            with SessionLocal() as db:
                cached_entry = (
                    db.query(OutputCache).filter(OutputCache.cache_key == cache_key).first()
                )
                if cached_entry:
                    passed, assertion_res = evaluate_assertions(cached_entry.output, assertions)
                    return {
                        "test_case_id": test_case_id,
                        "status": "passed" if passed else "failed",
                        "rendered_prompt": rendered,
                        "output": cached_entry.output,
                        "error_message": None,
                        "latency_ms": 0.0,
                        "prompt_tokens": cached_entry.prompt_tokens,
                        "completion_tokens": cached_entry.completion_tokens,
                        "total_tokens": cached_entry.total_tokens,
                        "cached": True,
                        "assertion_results": assertion_res,
                        "retry_count": 0,
                    }

        # 3. Model Generation with Rate Limiting and Jittered Exponential Backoff
        retries = 0
        last_error = ""
        while True:
            # Check cancellation again before calling model
            with SessionLocal() as db:
                current_run = db.query(Run).filter(Run.id == run_id).first()
                if current_run and current_run.status == "cancelled":
                    return {
                        "test_case_id": test_case_id,
                        "status": "cancelled",
                        "rendered_prompt": rendered,
                        "output": None,
                        "error_message": "Run was cancelled by user",
                        "latency_ms": 0.0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "cached": False,
                        "assertion_results": [],
                        "retry_count": retries,
                    }

            await rate_limiter.acquire()
            try:
                response = await client.generate_content(prompt=rendered, model=model)
                break
            except GeminiAuthError as auth_err:
                # Do not retry auth errors
                return {
                    "test_case_id": test_case_id,
                    "status": "error",
                    "rendered_prompt": rendered,
                    "output": None,
                    "error_message": f"Authentication error: {auth_err}",
                    "latency_ms": 0.0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cached": False,
                    "assertion_results": [],
                    "retry_count": retries,
                }
            except (GeminiRateLimitError, GeminiServerError) as retryable_err:
                retries += 1
                last_error = str(retryable_err)
                if retries > max_retries:
                    return {
                        "test_case_id": test_case_id,
                        "status": "error",
                        "rendered_prompt": rendered,
                        "output": None,
                        "error_message": f"Exceeded max retries ({max_retries}): {last_error}",
                        "latency_ms": 0.0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "cached": False,
                        "assertion_results": [],
                        "retry_count": retries,
                    }
                backoff_time = calculate_backoff(retries)
                await asyncio.sleep(backoff_time)
            except Exception as unk_err:
                return {
                    "test_case_id": test_case_id,
                    "status": "error",
                    "rendered_prompt": rendered,
                    "output": None,
                    "error_message": f"Unexpected execution error: {unk_err}",
                    "latency_ms": 0.0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cached": False,
                    "assertion_results": [],
                    "retry_count": retries,
                }

        # 4. Save to Output Cache
        if enable_cache and response.text:
            with SessionLocal() as db:
                try:
                    cache_item = OutputCache(
                        project_id=current_run.project_id if current_run else 1,
                        cache_key=cache_key,
                        output=response.text,
                        prompt_tokens=response.prompt_tokens,
                        completion_tokens=response.completion_tokens,
                        total_tokens=response.total_tokens,
                    )
                    db.add(cache_item)
                    db.commit()
                except Exception:
                    db.rollback()

        # 5. Evaluate assertions
        passed, assertion_res = evaluate_assertions(response.text, assertions)

        return {
            "test_case_id": test_case_id,
            "status": "passed" if passed else "failed",
            "rendered_prompt": rendered,
            "output": response.text,
            "error_message": None,
            "latency_ms": response.latency_ms,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "total_tokens": response.total_tokens,
            "cached": False,
            "assertion_results": assertion_res,
            "retry_count": retries,
        }


async def run_engine_executor(
    run_id: int,
    client: BaseGeminiClient | None = None,
    max_concurrency: int = 5,
    requests_per_minute: int = 6000,
    enable_cache: bool = True,
) -> None:
    """Execute a run with bounded concurrency, heartbeat updating, and SSE event streaming."""
    with SessionLocal() as db:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return

        if run.status in ("completed", "cancelled", "failed"):
            return

        project = db.query(Project).filter(Project.id == run.project_id).first()
        prompt_version = (
            db.query(PromptVersion).filter(PromptVersion.id == run.prompt_version_id).first()
        )
        if not prompt_version or not project:
            run.status = "failed"
            run.error_message = "Prompt version or project not found"
            db.commit()
            return

        # Fetch active test cases
        active_tests = (
            db.query(TestCase)
            .filter(TestCase.project_id == run.project_id, TestCase.is_active == True)  # noqa: E712
            .order_by(TestCase.id.asc())
            .all()
        )

        run.total_tests = len(active_tests)
        run.status = "running"
        run.started_at = datetime.now(UTC)
        run.heartbeat_at = datetime.now(UTC)
        db.commit()

        prompt_template = prompt_version.content

        # Determine Gemini Client
        if client is None:
            plain_key = ""
            if project.encrypted_gemini_api_key:
                try:
                    plain_key = decrypt_api_key(project.encrypted_gemini_api_key)
                except Exception:
                    plain_key = ""
            client = GeminiClient(api_key=plain_key)

        test_data_list = [(t.id, t.name, t.inputs, t.assertions) for t in active_tests]

    await broadcaster.emit(
        run_id,
        "run_started",
        {"run_id": run_id, "total_tests": len(test_data_list)},
    )

    semaphore = asyncio.Semaphore(max_concurrency)
    rate_limiter = RateLimiter(requests_per_minute=requests_per_minute)

    # Heartbeat updater task
    heartbeat_stop = asyncio.Event()

    async def _heartbeat_worker():
        while not heartbeat_stop.is_set():
            try:
                await asyncio.sleep(3.0)
                with SessionLocal() as db:
                    db_run = db.query(Run).filter(Run.id == run_id).first()
                    if db_run and db_run.status == "running":
                        db_run.heartbeat_at = datetime.now(UTC)
                        db.commit()
            except Exception:
                pass

    hb_task = asyncio.create_task(_heartbeat_worker())

    passed_count = 0
    failed_count = 0

    try:
        # Create asynchronous tasks for all tests with bounded concurrency
        async def _run_single(tid: int, tname: str, inputs: dict, assertions: list):
            nonlocal passed_count, failed_count

            res = await execute_test_case(
                run_id=run_id,
                test_case_id=tid,
                prompt_template=prompt_template,
                test_name=tname,
                inputs=inputs,
                assertions=assertions,
                client=client,
                rate_limiter=rate_limiter,
                semaphore=semaphore,
                enable_cache=enable_cache,
            )
            res["test_case_name"] = tname

            # Persist result to DB
            with SessionLocal() as db:
                # Check for cancellation
                db_run = db.query(Run).filter(Run.id == run_id).first()
                if db_run and db_run.status == "cancelled":
                    res["status"] = "cancelled"

                # Invariant: Duplicate result prevention (check if exists first)
                existing = (
                    db.query(RunResult)
                    .filter(RunResult.run_id == run_id, RunResult.test_case_id == tid)
                    .first()
                )
                if not existing:
                    run_result = RunResult(
                        run_id=run_id,
                        test_case_id=tid,
                        status=res["status"],
                        rendered_prompt=res["rendered_prompt"],
                        output=res["output"],
                        error_message=res["error_message"],
                        latency_ms=res["latency_ms"],
                        prompt_tokens=res["prompt_tokens"],
                        completion_tokens=res["completion_tokens"],
                        total_tokens=res["total_tokens"],
                        cached=res["cached"],
                        assertion_results=res["assertion_results"],
                        retry_count=res["retry_count"],
                    )
                    db.add(run_result)
                    db.commit()
                else:
                    existing.status = res["status"]
                    existing.output = res["output"]
                    existing.error_message = res["error_message"]
                    existing.latency_ms = res["latency_ms"]
                    existing.prompt_tokens = res["prompt_tokens"]
                    existing.completion_tokens = res["completion_tokens"]
                    existing.total_tokens = res["total_tokens"]
                    existing.cached = res["cached"]
                    existing.assertion_results = res["assertion_results"]
                    existing.retry_count = res["retry_count"]
                    db.commit()

            if res["status"] == "passed":
                passed_count += 1
            else:
                failed_count += 1

            # Emit test_result and run_progress SSE events
            await broadcaster.emit(run_id, "test_result", res)
            await broadcaster.emit(
                run_id,
                "run_progress",
                {
                    "run_id": run_id,
                    "passed": passed_count,
                    "failed": failed_count,
                    "total": len(test_data_list),
                    "completed": passed_count + failed_count,
                },
            )

        tasks = [
            _run_single(tid, tname, inputs, assertions)
            for (tid, tname, inputs, assertions) in test_data_list
        ]
        if tasks:
            await asyncio.gather(*tasks)

    finally:
        heartbeat_stop.set()
        hb_task.cancel()
        try:
            await hb_task
        except asyncio.CancelledError:
            pass

    # Finalize Run status
    with SessionLocal() as db:
        final_run = db.query(Run).filter(Run.id == run_id).first()
        if final_run:
            if final_run.status != "cancelled":
                final_run.status = "completed"
            final_run.passed_tests = passed_count
            final_run.failed_tests = failed_count
            final_run.completed_at = datetime.now(UTC)
            db.commit()

            final_event = "run_cancelled" if final_run.status == "cancelled" else "run_completed"
            await broadcaster.emit(
                run_id,
                final_event,
                {
                    "run_id": run_id,
                    "status": final_run.status,
                    "total_tests": final_run.total_tests,
                    "passed_tests": final_run.passed_tests,
                    "failed_tests": final_run.failed_tests,
                },
            )
