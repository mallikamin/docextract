"""Health check endpoint - deep checks for Tesseract, Poppler, Claude API, disk."""

import shutil
import subprocess
import logging
from datetime import datetime
from fastapi import APIRouter

from backend.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check():
    checks = {}
    all_ok = True

    # Tesseract
    try:
        result = subprocess.run(
            ["tesseract", "--version"], capture_output=True, text=True, timeout=5
        )
        version = result.stdout.split("\n")[0] if result.stdout else "unknown"
        checks["tesseract"] = {"status": "ok", "version": version}
    except Exception as e:
        checks["tesseract"] = {"status": "error", "message": str(e)}
        all_ok = False

    # Poppler (pdfinfo or pdftoppm)
    try:
        result = subprocess.run(
            ["pdftoppm", "-v"], capture_output=True, text=True, timeout=5
        )
        version = result.stderr.strip() if result.stderr else "unknown"
        checks["poppler"] = {"status": "ok", "version": version}
    except Exception as e:
        checks["poppler"] = {"status": "error", "message": str(e)}
        all_ok = False

    # Claude API key
    if settings.anthropic_api_key and settings.anthropic_api_key != "sk-ant-your-key-here":
        checks["claude_api"] = {"status": "ok", "key_configured": True}
    else:
        checks["claude_api"] = {"status": "warning", "message": "API key not configured"}

    # Disk space
    try:
        usage = shutil.disk_usage(str(settings.data_dir))
        free_gb = round(usage.free / (1024 ** 3), 1)
        checks["disk_space_gb"] = free_gb
        if free_gb < 1:
            all_ok = False
    except Exception:
        checks["disk_space_gb"] = "unknown"

    # Data dir writable
    checks["data_dir_writable"] = settings.data_dir.exists() and settings.data_dir.is_dir()

    status = "healthy" if all_ok else "degraded"
    status_code = 200 if all_ok else 503

    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
