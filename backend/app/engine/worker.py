import asyncio
from datetime import UTC, datetime, timedelta

from app.database import SessionLocal
from app.engine.client import BaseGeminiClient
from app.engine.runner import run_engine_executor
from app.models.run import Run


class BackgroundWorker:
    """
    Background worker implementing:
    - PostgreSQL SKIP LOCKED job claiming (Requirement 8 / 9)
    - Stuck-run reaper and crash recovery (Requirement 9 / 13)
    - Heartbeat monitoring and idempotent execution
    """

    def __init__(
        self,
        poll_interval: float = 0.5,
        stuck_threshold_seconds: float = 30.0,
        gemini_client: BaseGeminiClient | None = None,
    ):
        self.poll_interval = poll_interval
        self.stuck_threshold_seconds = stuck_threshold_seconds
        self.gemini_client = gemini_client
        self._running = False
        self._task: asyncio.Task | None = None

    def reap_stuck_runs(self, requeue: bool = False, max_recovery_attempts: int = 2) -> int:
        """
        Stuck-run reaper and recovery mechanism.
        Detects runs in 'running' state whose heartbeat is older than stuck_threshold_seconds.
        If requeue=True, requeues the run for worker restart recovery up to max_recovery_attempts.
        Otherwise or if attempts exceeded, marks the run as failed.
        """
        threshold = datetime.now(UTC) - timedelta(seconds=self.stuck_threshold_seconds)
        count = 0
        with SessionLocal() as db:
            stuck_runs = (
                db.query(Run).filter(Run.status == "running", Run.heartbeat_at < threshold).all()
            )
            for r in stuck_runs:
                current_summary = r.summary or {}
                attempts = current_summary.get("recovery_attempts", 0)
                if requeue and attempts < max_recovery_attempts:
                    r.status = "queued"
                    r.error_message = f"Recovered after worker heartbeat timeout (attempt {attempts + 1})"
                    r.heartbeat_at = datetime.now(UTC)
                    current_summary["recovery_attempts"] = attempts + 1
                    r.summary = current_summary
                else:
                    r.status = "failed"
                    r.error_message = (
                        f"Worker heartbeat timed out (no heartbeat for > "
                        f"{self.stuck_threshold_seconds}s)"
                    )
                    r.completed_at = datetime.now(UTC)
                count += 1
            if count > 0:
                db.commit()
        return count

    def recover_stuck_runs(self, max_recovery_attempts: int = 2) -> int:
        """Recover stuck runs by requeuing them."""
        return self.reap_stuck_runs(requeue=True, max_recovery_attempts=max_recovery_attempts)

    def claim_next_job(self) -> int | None:
        """
        Claim the next queued run using PostgreSQL SKIP LOCKED.
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
                if not claimed_run.started_at:
                    claimed_run.started_at = datetime.now(UTC)
                claimed_run.heartbeat_at = datetime.now(UTC)
                db.commit()
                return run_id
        return None

    async def run_once(self) -> bool:
        """Attempt to recover stuck runs and process one queued job."""
        self.recover_stuck_runs()
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
