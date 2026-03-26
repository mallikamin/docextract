# DocExtract - Intelligent PDF to CSV Extraction

**Professional document digitization system for financial institutions.**

Converts bank statements, invoices, receipts, and KYC documents into structured CSV with 90%+ accuracy using Claude AI + Tesseract OCR.

![DocExtract](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![Claude](https://img.shields.io/badge/Claude-4.5-7C3AED)

---

## Features

- **4 Document Types**: Bank Statements, Invoices, Receipts, KYC Documents
- **Smart CSV Output**: Summary (1 row/doc) + Transactions (1 row/transaction)
- **Real-time Progress**: Live SSE streaming with per-file stage indicators
- **Benchmark Reports**: HTML reports with charts, metrics, cost analysis
- **Production Ready**: Docker, nginx, health checks, error handling
- **Cost Effective**: ~$0.04 per document vs $2.50 manual entry

---

## Quick Start

### Local Development

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/docextract.git
cd docextract

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure API key
cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY=sk-ant-...

# 4. Run
python run.py

# 5. Open browser
open http://localhost:8000
```

### Docker (Production)

```bash
# Build and run
docker-compose -f docker/docker-compose.yml up -d

# Check health
curl http://localhost:8000/health
```

---

## Architecture

```
PDF Upload
    ↓
PDF → Images (PyMuPDF, 300 DPI)
    ↓
Preprocessing (OpenCV: deskew, denoise, contrast)
    ↓
OCR (Tesseract 5, 90%+ accuracy)
    ↓
Classification (Claude Haiku, <500ms, $0.0006)
    ↓
Extraction (Claude Sonnet, tool_use, schema-enforced)
    ↓
CSV Generation (adaptive: single-row or multi-row)
    ↓
Benchmark Report (HTML with charts)
```

**Backend:** FastAPI + asyncio + SSE
**Frontend:** HTML + htmx + Tailwind CSS (zero build)
**Intelligence:** Claude API (Haiku + Sonnet)
**OCR:** Tesseract 5 + OpenCV preprocessing

---

## Document Types

| Type | Fields Extracted | CSV Strategy |
|------|-----------------|-------------|
| **Invoice** | Vendor, invoice #, date, line items, total | Single row + line items in transactions |
| **Bank Statement** | Account #, period, transactions, balance | Single summary + multi-row transactions |
| **Receipt** | Merchant, date, items, total | Single row |
| **KYC Document** | Name, DOB, ID #, address, expiry | Single row |

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/upload` | POST | Upload PDFs (returns job_id) |
| `/api/jobs/{id}` | GET | Job status (canonical state) |
| `/api/jobs/{id}/stream` | GET | SSE live updates |
| `/api/jobs/{id}/download/csv` | GET | Download CSV (zip) |
| `/api/jobs/{id}/download/report` | GET | Download HTML report |
| `/health` | GET | System health check |

---

## Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional
HAIKU_MODEL=claude-haiku-4-5-20251001
SONNET_MODEL=claude-sonnet-4-5-20250929
OCR_DPI=300
MAX_FILE_SIZE_MB=50
```

---

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for:
- GitHub Actions CI/CD
- DuckDNS free domain setup
- VPS deployment (DigitalOcean, AWS, etc.)
- Custom domain + SSL

**Quick Deploy:**
```bash
# Push to GitHub
git push origin main

# Auto-deploys via GitHub Actions
# Get URL: https://your-subdomain.duckdns.org
```

---

## Cost Analysis

| Volume | Monthly Cost | Per Document | Time |
|--------|-------------|-------------|------|
| 100 docs | $4 | $0.042 | 14 min |
| 1,000 docs | $42 | $0.042 | 2.3 hrs |
| 10,000 docs | $210 | $0.021 | 23 hrs |

**vs. Manual Entry:** $2.50/doc (10 min @ $15/hr) = **98% cost savings**

---

## Performance

- **Classification:** <500ms (Claude Haiku)
- **Extraction:** 2-5s per document (Claude Sonnet)
- **OCR:** 1-3s per page (Tesseract)
- **Total:** ~8-12s per document

**Tested:** 91.4% OCR confidence on real scanned documents.

---

## Screenshots

### Upload Interface
Professional drag-drop with real-time progress bars per file.

### Results Dashboard
Document type badges, confidence scores, expandable field preview.

### Benchmark Report
Executive-ready HTML with charts, metrics, cost projections.

---

## Tech Stack

- **Backend:** Python 3.12, FastAPI, uvicorn
- **Frontend:** HTML5, htmx, Tailwind CSS (CDN)
- **OCR:** Tesseract 5, OpenCV
- **AI:** Claude 4.5 (Haiku + Sonnet)
- **Storage:** File-based (no database for demo)
- **Deployment:** Docker, nginx, Let's Encrypt

---

## Project Structure

```
docextract/
├── backend/
│   ├── api/          # FastAPI routes
│   ├── pipeline/     # PDF→CSV processing stages
│   ├── services/     # Claude client, event bus, job manager
│   ├── models/       # Pydantic schemas
│   └── templates/    # Jinja2 HTML report
├── frontend/
│   ├── index.html    # Single-page app
│   ├── css/          # Tailwind + custom styles
│   └── js/           # htmx + SSE handling
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── nginx/        # nginx config + SSL
├── tests/
│   └── fixtures/     # Sample PDFs
└── scripts/
    └── download_samples.py
```

---

## Testing

```bash
# Download sample PDFs
python scripts/download_samples.py

# Run tests
pytest tests/

# Check code
python -m pylint backend/
```

---

## License

Proprietary - Sitara Infotech

---

## Support

- **Email:** support@sitarainfotech.com
- **Issues:** GitHub Issues
- **Docs:** [DEPLOYMENT.md](DEPLOYMENT.md)

---

**Built by Sitara Infotech** | Powered by Claude AI + Tesseract OCR
