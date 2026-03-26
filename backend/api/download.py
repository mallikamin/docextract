"""Download endpoints for CSV and report files."""

import zipfile
import io
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from backend.services.job_manager import get_job, get_job_dir

router = APIRouter()


@router.get("/api/jobs/{job_id}/download/csv")
async def download_csv(job_id: str):
    """Download CSV output as a zip file (summary.csv + transactions.csv)."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status.value != "completed":
        raise HTTPException(409, "Job not yet completed")

    output_dir = get_job_dir(job_id) / "output"
    csv_files = list(output_dir.glob("*.csv"))

    if not csv_files:
        raise HTTPException(404, "No CSV files generated")

    # If single CSV, return directly
    if len(csv_files) == 1:
        return FileResponse(
            str(csv_files[0]),
            media_type="text/csv",
            filename=f"extraction_{job_id}.csv",
        )

    # Multiple CSVs: zip them
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for csv_path in csv_files:
            zf.write(csv_path, csv_path.name)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="extraction_{job_id}.zip"'},
    )


@router.get("/api/jobs/{job_id}/download/report")
async def download_report(job_id: str):
    """Download the benchmark HTML report."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    report_path = get_job_dir(job_id) / "output" / "report.html"
    if not report_path.exists():
        raise HTTPException(404, "Report not yet generated")

    return FileResponse(
        str(report_path),
        media_type="text/html",
        filename=f"benchmark_report_{job_id}.html",
    )
