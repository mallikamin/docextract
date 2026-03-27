#!/bin/bash
# Render sets PORT env var - use it or default to 8000
uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
