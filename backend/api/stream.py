"""SSE streaming endpoint for live job updates."""

import json
import logging

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from backend.services import event_bus
from backend.services.job_manager import get_job

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    """Server-Sent Events stream for real-time job updates."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")

    async def event_generator():
        async for event in event_bus.subscribe(job_id):
            event_type = event.get("event", "message")
            data = event.get("data", {})

            if event_type == "keepalive":
                yield {"event": "keepalive", "data": ""}
                continue

            yield {
                "event": event_type,
                "data": json.dumps(data),
            }

    return EventSourceResponse(event_generator())
