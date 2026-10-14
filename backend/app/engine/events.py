import asyncio
import json
from collections import defaultdict
from typing import Any


class RunEventBroadcaster:
    """Manages Server-Sent Events (SSE) subscribers for active evaluation runs."""

    def __init__(self):
        self._subscribers: dict[int, list[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, run_id: int) -> asyncio.Queue:
        """Subscribe to SSE events for a specific run."""
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._subscribers[run_id].append(queue)
        return queue

    async def unsubscribe(self, run_id: int, queue: asyncio.Queue) -> None:
        """Unsubscribe from a run's SSE events."""
        async with self._lock:
            if run_id in self._subscribers and queue in self._subscribers[run_id]:
                self._subscribers[run_id].remove(queue)
                if not self._subscribers[run_id]:
                    del self._subscribers[run_id]

    async def emit(self, run_id: int, event_type: str, payload: dict[str, Any]) -> None:
        """Broadcast an event to all subscribers listening to this run."""
        message = {
            "event": event_type,
            "data": payload,
        }
        async with self._lock:
            queues = list(self._subscribers.get(run_id, []))

        for q in queues:
            await q.put(message)

    @staticmethod
    def format_sse(event_type: str, data: dict[str, Any]) -> str:
        """Format an event and JSON data dictionary into standard SSE string."""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


broadcaster = RunEventBroadcaster()
