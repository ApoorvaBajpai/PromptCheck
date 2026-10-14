import asyncio
import time
from datetime import UTC, datetime, timedelta

import pytest

from app.database import SessionLocal
from app.engine.client import FakeGeminiClient
from app.engine.events import broadcaster
from app.engine.prompt_renderer import PromptRenderError, render_prompt
from app.engine.runner import run_engine_executor
from app.engine.worker import BackgroundWorker
from app.models.project import Project
from app.models.prompt import Prompt, PromptVersion
from app.models.run import Run, RunResult
from app.models.test_case import TestCase
from app.models.user import User


@pytest.fixture
def run_fixture():
    """Setup project, prompt, version, and test cases with dedicated committed session."""
    uid = f"run_user_{time.time()}_{id(object())}"
    with SessionLocal() as db:
        user = User(
            email=f"{uid}@example.com",
            hashed_password="hashed_pass_test",
            full_name="Run Test User",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        project = Project(user_id=user.id, name="Run Engine Project")
        db.add(project)
        db.commit()
        db.refresh(project)

        prompt = Prompt(project_id=project.id, name="Greeter Prompt")
        db.add(prompt)
        db.commit()
        db.refresh(prompt)

        version = PromptVersion(
            prompt_id=prompt.id,
            version_number=1,
            content="Hello {{ name }}, welcome to {{ place }}!",
            content_hash=f"hash_{time.time()}_{id(object())}",
        )
        db.add(version)
        db.commit()
        db.refresh(version)

        user_id = user.id
        p_id = project.id
        pr_id = prompt.id
        v_id = version.id

    yield p_id, pr_id, v_id

    # Clean up after test
    with SessionLocal() as db:
        u = db.query(User).filter(User.id == user_id).first()
        if u:
            db.delete(u)
            db.commit()


# 1. Critical Test: Successful 20-test run
@pytest.mark.asyncio
async def test_successful_20_test_run(run_fixture):
    project_id, prompt_id, version_id = run_fixture

    # Create 20 test cases
    with SessionLocal() as db:
        for i in range(1, 21):
            tc = TestCase(
                project_id=project_id,
                name=f"Test Case {i}",
                inputs={"name": f"User{i}", "place": "Acme Corp"},
                assertions=[{"type": "contains", "value": f"User{i}"}],
                is_active=True,
            )
            db.add(tc)

        run = Run(
            project_id=project_id,
            prompt_version_id=version_id,
            status="queued",
            total_tests=20,
        )
        db.add(run)
        db.commit()
        run_id = run.id

    client = FakeGeminiClient()
    for i in range(1, 21):
        client.set_response_for_prompt(f"User{i}", f"Hello User{i}, welcome to Acme Corp!")

    await run_engine_executor(run_id=run_id, client=client, max_concurrency=10)

    with SessionLocal() as db:
        final_run = db.query(Run).filter(Run.id == run_id).first()
        assert final_run.status == "completed"
        assert final_run.total_tests == 20
        assert final_run.passed_tests == 20
        assert final_run.failed_tests == 0

        results = db.query(RunResult).filter(RunResult.run_id == run_id).all()
        assert len(results) == 20
        for r in results:
            assert r.status == "passed"
            assert r.prompt_tokens > 0
            assert r.completion_tokens > 0
            assert r.total_tokens == r.prompt_tokens + r.completion_tokens
            assert r.latency_ms >= 0


# 2. Critical Test: Multiple concurrent tests with bounded concurrency
@pytest.mark.asyncio
async def test_multiple_concurrent_tests(run_fixture):
    project_id, prompt_id, version_id = run_fixture
    active_count = 0
    max_active = 0
    lock = asyncio.Lock()

    class ConcurrencyTrackingClient(FakeGeminiClient):
        async def generate_content(self, prompt: str, model: str = "gemini-1.5-flash"):
            nonlocal active_count, max_active
            async with lock:
                active_count += 1
                if active_count > max_active:
                    max_active = active_count
            await asyncio.sleep(0.05)
            async with lock:
                active_count -= 1
            return await super().generate_content(prompt, model)

    with SessionLocal() as db:
        for i in range(8):
            db.add(TestCase(
                project_id=project_id,
                name=f"Concurrent Test {i}",
                inputs={"name": f"User{i}", "place": "World"},
                assertions=[],
            ))
        run = Run(
            project_id=project_id,
            prompt_version_id=version_id,
            status="queued",
        )
        db.add(run)
        db.commit()
        run_id = run.id

    client = ConcurrencyTrackingClient(default_response="Hi User, welcome!")
    # Bound concurrency to max 3
    await run_engine_executor(run_id=run_id, client=client, max_concurrency=3)

    assert max_active <= 3
    assert max_active > 1


# 3. Critical Test: 429 Retry with exponential backoff
@pytest.mark.asyncio
async def test_429_retry(run_fixture):
    project_id, prompt_id, version_id = run_fixture
    with SessionLocal() as db:
        tc = TestCase(
            project_id=project_id,
            name="Retry 429 Test",
            inputs={"name": "Alice", "place": "Wonderland"},
            assertions=[{"type": "contains", "value": "Wonderland"}],
        )
        db.add(tc)
        run = Run(project_id=project_id, prompt_version_id=version_id, status="queued")
        db.add(run)
        db.commit()
        run_id = run.id

    client = FakeGeminiClient(default_response="Hello Alice, welcome to Wonderland!")
    # Fail first 2 calls with 429, then succeed on 3rd attempt
    client.set_fail_with_429(count=2)

    await run_engine_executor(run_id=run_id, client=client)

    with SessionLocal() as db:
        res = db.query(RunResult).filter(RunResult.run_id == run_id).first()
        assert res is not None
        assert res.status == "passed"
        assert res.retry_count == 2


# 4. Critical Test: 500 Retry with exponential backoff
@pytest.mark.asyncio
async def test_500_retry(run_fixture):
    project_id, prompt_id, version_id = run_fixture
    with SessionLocal() as db:
        tc = TestCase(
            project_id=project_id,
            name="Retry 500 Test",
            inputs={"name": "Bob", "place": "Earth"},
            assertions=[{"type": "contains", "value": "Earth"}],
        )
        db.add(tc)
        run = Run(project_id=project_id, prompt_version_id=version_id, status="queued")
        db.add(run)
        db.commit()
        run_id = run.id

    client = FakeGeminiClient(default_response="Hello Bob, welcome to Earth!")
    # Fail first 2 calls with 500, then succeed on 3rd attempt
    client.set_fail_with_500(count=2)

    await run_engine_executor(run_id=run_id, client=client)

    with SessionLocal() as db:
        res = db.query(RunResult).filter(RunResult.run_id == run_id).first()
        assert res is not None
        assert res.status == "passed"
        assert res.retry_count == 2


# 5. Critical Test: Invalid API Key
@pytest.mark.asyncio
async def test_invalid_api_key(run_fixture):
    project_id, prompt_id, version_id = run_fixture
    with SessionLocal() as db:
        tc = TestCase(
            project_id=project_id,
            name="Auth Fail Test",
            inputs={"name": "Carol", "place": "Moon"},
            assertions=[],
        )
        db.add(tc)
        run = Run(project_id=project_id, prompt_version_id=version_id, status="queued")
        db.add(run)
        db.commit()
        run_id = run.id

    client = FakeGeminiClient()
    client.set_invalid_api_key(True)

    await run_engine_executor(run_id=run_id, client=client)

    with SessionLocal() as db:
        res = db.query(RunResult).filter(RunResult.run_id == run_id).first()
        assert res is not None
        assert res.status == "error"
        assert "Authentication error" in res.error_message


# 6. Critical Test: Worker crash and restart with SKIP LOCKED job claiming
@pytest.mark.asyncio
async def test_worker_crash_and_restart(run_fixture):
    project_id, prompt_id, version_id = run_fixture
    with SessionLocal() as db:
        tc = TestCase(
            project_id=project_id,
            name="Worker Test",
            inputs={"name": "David", "place": "Mars"},
            assertions=[],
        )
        db.add(tc)
        run1 = Run(project_id=project_id, prompt_version_id=version_id, status="queued")
        run2 = Run(project_id=project_id, prompt_version_id=version_id, status="queued")
        db.add(run1)
        db.add(run2)
        db.commit()
        r1_id = run1.id
        r2_id = run2.id

    worker1 = BackgroundWorker(gemini_client=FakeGeminiClient())
    # Worker 1 claims job 1
    claimed_1 = worker1.claim_next_job()
    assert claimed_1 == r1_id

    # Worker 1 "crashes" before completing (does not process claimed_1 further)
    # Worker 2 starts up, claims the next available queued job using SKIP LOCKED
    worker2 = BackgroundWorker(gemini_client=FakeGeminiClient())
    claimed_2 = worker2.claim_next_job()
    assert claimed_2 == r2_id

    # Verify run2 completes when executed by worker2
    await run_engine_executor(run_id=r2_id, client=worker2.gemini_client)
    with SessionLocal() as db:
        run2_db = db.query(Run).filter(Run.id == r2_id).first()
        assert run2_db.status == "completed"


# 7. Critical Test: Duplicate result prevention
@pytest.mark.asyncio
async def test_duplicate_result_prevention(run_fixture):
    project_id, prompt_id, version_id = run_fixture
    with SessionLocal() as db:
        tc = TestCase(
            project_id=project_id,
            name="Dedup Result Test",
            inputs={"name": "Eve", "place": "Venus"},
            assertions=[],
        )
        db.add(tc)
        run = Run(project_id=project_id, prompt_version_id=version_id, status="queued")
        db.add(run)
        db.commit()
        run_id = run.id

    client = FakeGeminiClient(default_response="Hello Eve, welcome to Venus!")

    # Run execution first time
    await run_engine_executor(run_id=run_id, client=client)

    # Run execution a second time (e.g. retry / resume)
    await run_engine_executor(run_id=run_id, client=client)

    with SessionLocal() as db:
        # Must only have 1 result row for the run and test_case, not duplicates
        results = db.query(RunResult).filter(RunResult.run_id == run_id).all()
        assert len(results) == 1
        assert results[0].status == "passed"


# 8. Critical Test: Run Cancellation
@pytest.mark.asyncio
async def test_cancellation(run_fixture):
    project_id, prompt_id, version_id = run_fixture
    with SessionLocal() as db:
        for i in range(5):
            db.add(TestCase(
                project_id=project_id,
                name=f"Cancel Test {i}",
                inputs={"name": f"User{i}", "place": "Space"},
                assertions=[],
            ))
        run = Run(project_id=project_id, prompt_version_id=version_id, status="queued")
        db.add(run)
        db.commit()
        run_id = run.id

    class SlowClient(FakeGeminiClient):
        async def generate_content(self, prompt: str, model: str = "gemini-1.5-flash"):
            await asyncio.sleep(0.1)
            return await super().generate_content(prompt, model)

    async def _cancel_after_delay():
        await asyncio.sleep(0.05)
        with SessionLocal() as db:
            db_run = db.query(Run).filter(Run.id == run_id).first()
            if db_run:
                db_run.status = "cancelled"
                db.commit()

    cancel_task = asyncio.create_task(_cancel_after_delay())
    await run_engine_executor(run_id=run_id, client=SlowClient(), max_concurrency=1)
    await cancel_task

    with SessionLocal() as db:
        final_run = db.query(Run).filter(Run.id == run_id).first()
        assert final_run.status == "cancelled"


# 9. Critical Test: Stuck worker recovery (Heartbeat timeout reaper)
def test_stuck_worker_recovery(run_fixture):
    project_id, prompt_id, version_id = run_fixture
    with SessionLocal() as db:
        old_heartbeat = datetime.now(UTC) - timedelta(seconds=45)
        stuck_run = Run(
            project_id=project_id,
            prompt_version_id=version_id,
            status="running",
            heartbeat_at=old_heartbeat,
        )
        db.add(stuck_run)
        db.commit()
        stuck_id = stuck_run.id

    worker = BackgroundWorker(stuck_threshold_seconds=30.0)
    reaped = worker.reap_stuck_runs()
    assert reaped >= 1

    with SessionLocal() as db:
        r = db.query(Run).filter(Run.id == stuck_id).first()
        assert r.status == "failed"
        assert "heartbeat timed out" in r.error_message


# 10. Critical Test: SSE Event Streaming
@pytest.mark.asyncio
async def test_sse_events(run_fixture):
    project_id, prompt_id, version_id = run_fixture
    with SessionLocal() as db:
        tc = TestCase(
            project_id=project_id,
            name="SSE Test",
            inputs={"name": "Grace", "place": "Jupiter"},
            assertions=[{"type": "contains", "value": "Jupiter"}],
        )
        db.add(tc)
        run = Run(project_id=project_id, prompt_version_id=version_id, status="queued")
        db.add(run)
        db.commit()
        run_id = run.id

    queue = await broadcaster.subscribe(run_id)

    client = FakeGeminiClient(default_response="Hello Grace, welcome to Jupiter!")
    await run_engine_executor(run_id=run_id, client=client)

    events_received = []
    while not queue.empty():
        msg = await queue.get()
        events_received.append(msg["event"])

    await broadcaster.unsubscribe(run_id, queue)

    assert "run_started" in events_received
    assert "test_result" in events_received
    assert "run_progress" in events_received
    assert "run_completed" in events_received


# 11. Jinja2 Sandboxed Rendering Error Test
def test_jinja2_sandbox_error():
    with pytest.raises(PromptRenderError):
        render_prompt("Hello {{ missing_variable }}", {})

    with pytest.raises(PromptRenderError):
        render_prompt("Unclosed tag {{ name ", {"name": "Alice"})
