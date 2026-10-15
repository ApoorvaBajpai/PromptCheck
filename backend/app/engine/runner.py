import asyncio
import hashlib
import inspect
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.security import decrypt_api_key
from app.database import SessionLocal
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
from app.engine.regression import apply_regression_analysis_to_run, calculate_test_score
from app.evaluators import EvaluationContext, evaluate_all
from app.models.project import Project
from app.models.prompt import PromptVersion
from app.models.run import OutputCache, Run, RunResult
from app.models.test_case import TestCase

DEFAULT_CACHE_TTL_DAYS = 7


def compute_output_cache_key(
    project_id: int,
    model: str,
    rendered_prompt: str,
    system_instruction: str | None = None,
    temperature: float = 1.0,
    top_p: float | None = None,
    max_output_tokens: int | None = None,
    response_mime_type: str | None = None,
) -> str:
    """
    Compute deterministic SHA-256 cache key including all inputs affecting model output.
    Ensures cache entries are strictly scoped to project identity.
    """
    payload = (
        f"proj:{project_id}|m:{model}|p:{rendered_prompt}|si:{system_instruction or ''}|"
        f"t:{temperature:.4f}|tp:{top_p or ''}|mot:{max_output_tokens or ''}|fmt:{response_mime_type or ''}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def execute_test_case(
    run_id: int,
    project_id: int,
    test_case_id: int,
    repeat_index: int,
    prompt_template: str,
    test_name: str,
    inputs: dict[str, Any],
    assertions: list[dict[str, Any]],
    client: BaseGeminiClient,
    rate_limiter: RateLimiter,
    semaphore: asyncio.Semaphore,
    model: str = "gemini-2.5-flash",
    system_instruction: str | None = None,
    temperature: float = 1.0,
    top_p: float | None = None,
    max_output_tokens: int | None = None,
    response_mime_type: str | None = None,
    enable_cache: bool = True,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Execute a single test case with bounded concurrency, project-scoped caching, rate limiting, and backoff."""
    async with semaphore:
        # Check cancellation state before running
        with SessionLocal() as db:
            current_run = db.query(Run).filter(Run.id == run_id).first()
            if current_run and current_run.status == "cancelled":
                return {
                    "test_case_id": test_case_id,
                    "repeat_index": repeat_index,
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
                "repeat_index": repeat_index,
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
        # IMPORTANT: Repeat executions (repeat_index > 0) MUST bypass cache to measure model variability
        cache_key = compute_output_cache_key(
            project_id=project_id,
            model=model,
            rendered_prompt=rendered,
            system_instruction=system_instruction,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
            response_mime_type=response_mime_type,
        )

        should_check_cache = enable_cache and (repeat_index == 0)
        if should_check_cache:
            now = datetime.now(UTC)
            with SessionLocal() as db:
                cached_entry = (
                    db.query(OutputCache)
                    .filter(
                        OutputCache.project_id == project_id,
                        OutputCache.cache_key == cache_key,
                        OutputCache.expires_at.is_(None) | (OutputCache.expires_at > now),
                    )
                    .first()
                )
                if cached_entry:
                    passed, assertion_res = await evaluate_all(
                        cached_entry.output,
                        assertions,
                        client=client,
                        context=EvaluationContext(
                            rendered_prompt=rendered,
                            test_inputs=inputs,
                            test_case_name=test_name,
                        ),
                    )
                    return {
                        "test_case_id": test_case_id,
                        "repeat_index": repeat_index,
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
                        "repeat_index": repeat_index,
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
                gen_fn = getattr(client, "generate_content", None)
                gen_kwargs: dict[str, Any] = {
                    "prompt": rendered,
                    "model": model,
                    "temperature": temperature,
                    "system_instruction": system_instruction,
                    "top_p": top_p,
                    "max_output_tokens": max_output_tokens,
                    "response_mime_type": response_mime_type,
                }
                if gen_fn and hasattr(inspect, "signature"):
                    try:
                        sig = inspect.signature(gen_fn)
                        has_var_kwargs = any(
                            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
                        )
                        if not has_var_kwargs:
                            gen_kwargs = {k: v for k, v in gen_kwargs.items() if k in sig.parameters}
                    except (ValueError, TypeError):
                        pass
                response = await client.generate_content(**gen_kwargs)
                break
            except GeminiAuthError as auth_err:
                # Do not retry auth errors
                return {
                    "test_case_id": test_case_id,
                    "repeat_index": repeat_index,
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
                        "repeat_index": repeat_index,
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
                    "repeat_index": repeat_index,
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

        # 4. Save to Output Cache (with project identity and TTL expiration)
        if enable_cache and response.text and repeat_index == 0:
            with SessionLocal() as db:
                try:
                    expires_at = datetime.now(UTC) + timedelta(days=DEFAULT_CACHE_TTL_DAYS)
                    existing_cache = (
                        db.query(OutputCache)
                        .filter(
                            OutputCache.project_id == project_id,
                            OutputCache.cache_key == cache_key,
                        )
                        .first()
                    )
                    if not existing_cache:
                        cache_item = OutputCache(
                            project_id=project_id,
                            cache_key=cache_key,
                            output=response.text,
                            prompt_tokens=response.prompt_tokens,
                            completion_tokens=response.completion_tokens,
                            total_tokens=response.total_tokens,
                            expires_at=expires_at,
                        )
                        db.add(cache_item)
                        db.commit()
                except Exception:
                    db.rollback()

        # 5. Evaluate assertions using Evaluator framework
        passed, assertion_res = await evaluate_all(
            response.text,
            assertions,
            client=client,
            context=EvaluationContext(
                rendered_prompt=rendered,
                test_inputs=inputs,
                test_case_name=test_name,
            ),
        )

        return {
            "test_case_id": test_case_id,
            "repeat_index": repeat_index,
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
    """
    Execute a run with bounded concurrency, repeatable test iterations,
    heartbeat monitoring, failure recovery, and SSE event streaming.
    """
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
            run.completed_at = datetime.now(UTC)
            db.commit()
            return

        # Fetch active test cases
        active_tests = (
            db.query(TestCase)
            .filter(TestCase.project_id == run.project_id, TestCase.is_active == True)  # noqa: E712
            .order_by(TestCase.id.asc())
            .all()
        )

        repeat_count = max(1, run.repeat_count or 1)
        total_executions = len(active_tests) * repeat_count
        run.total_tests = len(active_tests)
        run.status = "running"
        run.started_at = datetime.now(UTC)
        run.heartbeat_at = datetime.now(UTC)
        db.commit()

        project_id = project.id
        prompt_template = prompt_version.content
        model_name = prompt_version.model or "gemini-2.5-flash"
        system_instruction = prompt_version.system_instruction
        temperature = prompt_version.temperature if prompt_version.temperature is not None else 1.0
        top_p = prompt_version.top_p
        max_output_tokens = prompt_version.max_output_tokens
        response_mime_type = prompt_version.response_mime_type

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
        {"run_id": run_id, "total_tests": len(test_data_list), "repeat_count": repeat_count},
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
        # Check for existing completed results (e.g. if worker crashed and restarted)
        already_completed: set[tuple[int, int]] = set()
        with SessionLocal() as db:
            existing_results = (
                db.query(RunResult.test_case_id, RunResult.repeat_index)
                .filter(RunResult.run_id == run_id, RunResult.status.in_(("passed", "failed", "error", "cancelled")))
                .all()
            )
            for tid, rep_idx in existing_results:
                already_completed.add((tid, rep_idx))

        async def _run_single(tid: int, tname: str, inputs: dict, assertions: list, rep_idx: int):
            nonlocal passed_count, failed_count

            # If already executed before worker restart, skip duplicate execution
            if (tid, rep_idx) in already_completed:
                return

            res = await execute_test_case(
                run_id=run_id,
                project_id=project_id,
                test_case_id=tid,
                repeat_index=rep_idx,
                prompt_template=prompt_template,
                test_name=tname,
                inputs=inputs,
                assertions=assertions,
                client=client,
                rate_limiter=rate_limiter,
                semaphore=semaphore,
                model=model_name,
                system_instruction=system_instruction,
                temperature=temperature,
                top_p=top_p,
                max_output_tokens=max_output_tokens,
                response_mime_type=response_mime_type,
                enable_cache=enable_cache,
            )
            res["test_case_name"] = tname

            # Persist result to DB
            with SessionLocal() as db:
                # Check for cancellation
                db_run = db.query(Run).filter(Run.id == run_id).first()
                if db_run and db_run.status == "cancelled":
                    res["status"] = "cancelled"

                test_score = calculate_test_score(res["status"], res["assertion_results"])

                # Invariant: Duplicate result prevention by (run_id, test_case_id, repeat_index)
                existing = (
                    db.query(RunResult)
                    .filter(
                        RunResult.run_id == run_id,
                        RunResult.test_case_id == tid,
                        RunResult.repeat_index == rep_idx,
                    )
                    .first()
                )
                if not existing:
                    run_result = RunResult(
                        run_id=run_id,
                        test_case_id=tid,
                        repeat_index=rep_idx,
                        status=res["status"],
                        rendered_prompt=res["rendered_prompt"],
                        output=res["output"],
                        error_message=res["error_message"],
                        latency_ms=res["latency_ms"],
                        prompt_tokens=res["prompt_tokens"],
                        completion_tokens=res["completion_tokens"],
                        total_tokens=res["total_tokens"],
                        cached=res["cached"],
                        score=test_score,
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
                    existing.score = test_score
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
                    "total": total_executions,
                    "completed": passed_count + failed_count,
                },
            )

        tasks = []
        for (tid, tname, inputs, assertions) in test_data_list:
            for rep_idx in range(repeat_count):
                tasks.append(_run_single(tid, tname, inputs, assertions, rep_idx))

        if tasks:
            await asyncio.gather(*tasks)

    except Exception as run_err:
        with SessionLocal() as db:
            fail_run = db.query(Run).filter(Run.id == run_id).first()
            if fail_run and fail_run.status != "cancelled":
                fail_run.status = "failed"
                fail_run.error_message = f"Execution engine error: {run_err}"
                fail_run.completed_at = datetime.now(UTC)
                db.commit()
                await broadcaster.emit(
                    run_id,
                    "run_failed",
                    {"run_id": run_id, "error": str(run_err)},
                )
        return
    finally:
        heartbeat_stop.set()
        hb_task.cancel()
        try:
            await hb_task
        except asyncio.CancelledError:
            pass

    # Finalize Run status and compute Phase 4 regressions
    with SessionLocal() as db:
        final_run = db.query(Run).filter(Run.id == run_id).first()
        if final_run:
            if final_run.status != "cancelled":
                final_run.status = "completed"
            final_run.passed_tests = passed_count
            final_run.failed_tests = failed_count
            final_run.completed_at = datetime.now(UTC)
            db.commit()

            if final_run.status == "completed":
                try:
                    apply_regression_analysis_to_run(
                        db, final_run.id, explicit_baseline_id=final_run.baseline_run_id
                    )
                    db.refresh(final_run)
                except Exception as exc:
                    final_run.summary = {"error": f"Regression analysis failed: {exc}"}
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
                    "summary": final_run.summary,
                    "baseline_run_id": final_run.baseline_run_id,
                },
            )
