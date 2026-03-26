"""Job status endpoint - canonical source of truth for job state."""

from fastapi import APIRouter, HTTPException

from backend.services.job_manager import get_job

router = APIRouter()


@router.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get full job status including documents, metrics, and download URLs."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")

    return job.model_dump(exclude={"extractions"})
