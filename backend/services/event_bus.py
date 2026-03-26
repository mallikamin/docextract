"""In-memory pub/sub event bus for SSE streaming.

Each job gets its own asyncio.Queue. The orchestrator publishes events;
the SSE endpoint subscribes and yields them.
"""

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict

logger = logging.getLogger(__name__)

# Global registry: job_id -> list of subscriber queues
_subscribers: Dict[str, list] = {}


async def publish(job_id: str, event_type: str, data: dict):
    """Publish an event to all subscribers of a job."""
    if job_id not in _subscribers:
        return
    event = {"event": event_type, "data": data}
    dead = []
    for i, queue in enumerate(_subscribers[job_id]):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            dead.append(i)
    # Remove dead queues
    for i in reversed(dead):
        _subscribers[job_id].pop(i)


async def subscribe(job_id: str) -> AsyncGenerator[Dict[str, Any], None]:
    """Subscribe to events for a job. Yields event dicts."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.setdefault(job_id, []).append(queue)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield event
                if event.get("event") == "completed" or event.get("event") == "error":
                    break
            except asyncio.TimeoutError:
                # Send keepalive
                yield {"event": "keepalive", "data": {}}
    finally:
        if job_id in _subscribers and queue in _subscribers[job_id]:
            _subscribers[job_id].remove(queue)
        if job_id in _subscribers and not _subscribers[job_id]:
            del _subscribers[job_id]
