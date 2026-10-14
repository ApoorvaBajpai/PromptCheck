import asyncio
from datetime import UTC, datetime, timedelta

from app.database import SessionLocal
from app.engine.client import BaseGeminiClient
from app.engine.runner import run_engine_executor
from app.models.run import Run


class BackgroundWorker:
    """
    Background worker implementing:
    - PostgreSQL SKIP LOCKED job claiming (Requirement 8)
    - Stuck-run reaper (Requirement 13)
    - Heartbeat monitoring
    """

    def __init__(
        self,
        poll_interval: float = 1.0,
        stuck_threshold_seconds: float = 30.0,
        gemini_client: BaseGeminiClient | None = None,
    ):
        self.poll_interval = poll_interval
        self.stuck_threshold_seconds = stuck_threshold_seconds
        self.gemini_client = gemini_client
        self._running = False
        self._task: asyncio.Task | None = None

    def reap_stuck_runs(self) -> int:
        """
        Stuck-run reaper (Requirement 13).
        Detects runs in 'running' state whose heartbeat is older than stuck_threshold_seconds,
        marking them as failed.
        """
        threshold = datetime.now(UTC) - timedelta(seconds=self.stuck_threshold_seconds)
        reaped_count = 0
        with SessionLocal() as db:
            stuck_runs = (
                db.query(Run).filter(Run.status == "running", Run.heartbeat_at < threshold).all()
            )
            for r in stuck_runs:
                r.status = "failed"
                r.error_message = (
                    f"Worker heartbeat timed out (no heartbeat for > "
                    f"{self.stuck_threshold_seconds}s)"
                )
                r.completed_at = datetime.now(UTC)
                reaped_count += 1
            if reaped_count > 0:
                db.commit()
        return reaped_count

    def claim_next_job(self) -> int | None:
        """
        Claim the next queued run using PostgreSQL SKIP LOCKED (Requirement 8).
        Guarantees concurrency safety across multiple workers.
        """
        with SessionLocal() as db:
            claimed_run = (
                db.query(Run)
                .filter(Run.status == "queued")
                .order_by(Run.created_at.asc())
                .with_for_update(skip_locked=True)
                .first()
            )
            if claimed_run:
                run_id = claimed_run.id
                claimed_run.status = "running"
                claimed_run.started_at = datetime.now(UTC)
                claimed_run.heartbeat_at = datetime.now(UTC)
                db.commit()
                return run_id
        return None

    async def run_once(self) -> bool:
        """Attempt to reap stuck runs and process one queued job."""
        self.reap_stuck_runs()
        run_id = self.claim_next_job()
        if run_id:
            await run_engine_executor(run_id=run_id, client=self.gemini_client)
            return True
        return False

    async def _loop(self) -> None:
        while self._running:
            try:
                processed = await self.run_once()
                if not processed:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(self.poll_interval)

    def start(self) -> None:
        """Start worker in background event loop."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Stop worker cleanly."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


worker_instance = BackgroundWorker()
