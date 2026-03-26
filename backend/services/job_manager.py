"""File-based job storage. Each job is a JSON file in data/jobs/{job_id}/."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from backend.config import settings
from backend.models.schemas import Job, JobStatus, UploadResponse

logger = logging.getLogger(__name__)


def create_job(file_count: int) -> Job:
    """Create a new job with a unique ID and prepare its directory."""
    job_id = str(uuid4())[:12]
    job_dir = settings.jobs_dir / job_id

    # Create subdirectories
    for sub in ["input", "images", "preprocessed", "ocr", "extraction", "output"]:
        (job_dir / sub).mkdir(parents=True, exist_ok=True)

    job = Job(
        job_id=job_id,
        status=JobStatus.QUEUED,
        file_count=file_count,
        created_at=datetime.utcnow(),
    )
    _save_job(job)
    return job


def get_job(job_id: str) -> Optional[Job]:
    """Load a job from disk."""
    job_file = settings.jobs_dir / job_id / "job.json"
    if not job_file.exists():
        return None
    try:
        data = json.loads(job_file.read_text(encoding="utf-8"))
        return Job(**data)
    except Exception as e:
        logger.error("Failed to load job %s: %s", job_id, e)
        return None


def update_job(job: Job):
    """Persist job state to disk."""
    _save_job(job)


def get_job_dir(job_id: str) -> Path:
    """Return the directory for a job."""
    return settings.jobs_dir / job_id


def _save_job(job: Job):
    """Write job JSON to disk."""
    job_dir = settings.jobs_dir / job.job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    job_file = job_dir / "job.json"
    job_file.write_text(
        job.model_dump_json(indent=2),
        encoding="utf-8",
    )
