"""DocExtract - FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api import download, health, jobs, stream, upload
from backend.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    settings.ensure_dirs()
    logger.info("DocExtract started. Data dir: %s", settings.data_dir)
    yield
    logger.info("DocExtract shutting down.")


app = FastAPI(
    title="DocExtract",
    description="Intelligent PDF to CSV extraction for financial documents",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS (permissive for demo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(health.router)
app.include_router(upload.router)
app.include_router(jobs.router)
app.include_router(download.router)
app.include_router(stream.router)

# Serve frontend as static files
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
