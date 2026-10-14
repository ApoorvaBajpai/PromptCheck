import asyncio
import random
import time


class RateLimiter:
    """Async token bucket rate limiter for LLM requests per minute (RPM)."""

    def __init__(self, requests_per_minute: int = 60):
        self.capacity = max(1, requests_per_minute)
        self.tokens = float(self.capacity)
        self.fill_rate = self.capacity / 60.0  # tokens per second
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, waiting asynchronously if rate limit is reached."""
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(float(self.capacity), self.tokens + elapsed * self.fill_rate)

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

                # Calculate wait time needed for next token
                needed = 1.0 - self.tokens
                wait_time = needed / self.fill_rate
                await asyncio.sleep(min(wait_time, 1.0))


def calculate_backoff(
    retry_count: int,
    base_delay: float = 0.05,
    max_delay: float = 2.0,
    jitter: float = 0.2,
) -> float:
    """Calculate exponential backoff duration with random jitter."""
    delay = base_delay * (2**retry_count)
    delay += random.uniform(0, jitter * delay)
    return min(delay, max_delay)
