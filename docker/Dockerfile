FROM python:3.12-slim

# System dependencies: Tesseract + Poppler
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY start.sh ./

# Runtime directories
RUN mkdir -p /app/data/jobs && chmod +x /app/start.sh

EXPOSE 8000

CMD ["./start.sh"]
