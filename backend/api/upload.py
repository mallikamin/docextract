"""Upload endpoint - accepts PDFs, creates job, kicks off processing."""

import logging
from typing import List

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from backend.config import settings
from backend.models.schemas import UploadResponse
from backend.pipeline.orchestrator import process_job
from backend.services.job_manager import create_job, get_job_dir

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_SIZE = settings.max_file_size_mb * 1024 * 1024  # bytes


@router.post("/api/upload", response_model=UploadResponse, status_code=202)
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
):
    """Upload one or more PDF files for processing."""
    if not files:
        raise HTTPException(400, "No files provided")

    # Validate files
    pdf_files = []
    for f in files:
        if not f.filename or not f.filename.lower().endswith(".pdf"):
            raise HTTPException(400, f"Only PDF files accepted. Got: {f.filename}")

        content = await f.read()
        if len(content) > MAX_SIZE:
            raise HTTPException(400, f"File {f.filename} exceeds {settings.max_file_size_mb}MB limit")
        if not content[:4] == b"%PDF":
            raise HTTPException(400, f"File {f.filename} is not a valid PDF")

        pdf_files.append((f.filename, content))

    # Create job
    job = create_job(file_count=len(pdf_files))
    job_dir = get_job_dir(job.job_id)

    # Save files to input directory
    for filename, content in pdf_files:
        file_path = job_dir / "input" / filename
        file_path.write_bytes(content)

    logger.info("Job %s created: %d files", job.job_id, len(pdf_files))

    # Kick off background processing
    background_tasks.add_task(process_job, job.job_id)

    return UploadResponse(
        job_id=job.job_id,
        status="queued",
        file_count=len(pdf_files),
        created_at=job.created_at,
        stream_url=f"/api/jobs/{job.job_id}/stream",
    )
