"""Generate the benchmark HTML report from job results."""

import logging
from datetime import datetime
from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader

from backend.models.schemas import ExtractionResult, JobMetrics

logger = logging.getLogger(__name__)

# Colors for document types
DOC_TYPE_COLORS = {
    "bank_statement": "#22c55e",
    "invoice": "#3b82f6",
    "receipt": "#a855f7",
    "kyc_document": "#eab308",
    "unknown": "#94a3b8",
}

DOC_TYPE_BADGES = {
    "bank_statement": "green",
    "invoice": "blue",
    "receipt": "purple",
    "kyc_document": "yellow",
    "unknown": "blue",
}

STAGE_COLORS = {
    "PDF Conversion": "#3b82f6",
    "Preprocessing": "#8b5cf6",
    "OCR": "#ec4899",
    "Classification": "#f59e0b",
    "Extraction": "#22c55e",
}


def generate_report(
    job_id: str,
    extractions: List[ExtractionResult],
    metrics: JobMetrics,
    output_dir: Path,
) -> Path:
    """Generate a self-contained HTML benchmark report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.html"

    # Template directory
    template_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("report.html")

    # Calculate metrics
    total_docs = len(extractions)
    successful = [e for e in extractions if not e.error]

    avg_confidence = 0
    if successful:
        confidences = [e.classification_confidence for e in successful]
        avg_confidence = round(sum(confidences) / len(confidences) * 100)

    cost_per_doc = metrics.estimated_cost_usd / max(total_docs, 1)

    # Document type chart data
    type_counts = {}
    for e in extractions:
        t = e.doc_type.value
        type_counts[t] = type_counts.get(t, 0) + 1

    circumference = 439.82  # 2 * pi * 70
    doc_type_chart = []
    for dtype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        pct = count / max(total_docs, 1)
        doc_type_chart.append({
            "label": dtype.replace("_", " ").title(),
            "count": count,
            "color": DOC_TYPE_COLORS.get(dtype, "#94a3b8"),
            "arc": round(circumference * pct, 2),
        })

    # Time chart
    total_time = max(metrics.total_time_seconds, 0.1)
    ocr_time = metrics.ocr_time_seconds
    llm_time = metrics.llm_time_seconds
    other_time = max(total_time - ocr_time - llm_time, 0)

    # Estimate stage breakdown
    conversion_time = round(other_time * 0.4, 1)
    preprocess_time = round(other_time * 0.3, 1)
    csv_time = round(other_time * 0.3, 1)

    time_stages = [
        ("PDF Conversion", conversion_time),
        ("Preprocessing", preprocess_time),
        ("OCR", round(ocr_time, 1)),
        ("Classification", round(llm_time * 0.2, 1)),
        ("Extraction", round(llm_time * 0.8, 1)),
    ]
    max_time = max(t for _, t in time_stages) if time_stages else 1

    time_chart = []
    for label, value in time_stages:
        time_chart.append({
            "label": label,
            "value": value,
            "pct": round((value / max(total_time, 0.1)) * 100),
            "color": STAGE_COLORS.get(label, "#94a3b8"),
        })

    # Per-document table
    documents = []
    for e in extractions:
        field_count = len([k for k in e.fields if not k.startswith("_")])
        documents.append({
            "filename": e.filename,
            "doc_type": e.doc_type.value.replace("_", " ").title(),
            "badge_color": DOC_TYPE_BADGES.get(e.doc_type.value, "blue"),
            "page_count": e.page_count,
            "fields_count": field_count,
            "confidence": round(e.classification_confidence * 100),
            "time": round(e.processing_time_ms / 1000, 1),
        })

    # Sample extractions (first 5)
    samples = []
    for e in successful[:5]:
        samples.append({
            "filename": e.filename,
            "doc_type": e.doc_type.value.replace("_", " ").title(),
            "badge_color": DOC_TYPE_BADGES.get(e.doc_type.value, "blue"),
            "fields": e.fields,
        })

    # Render template
    html = template.render(
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        job_id=job_id,
        total_docs=total_docs,
        total_time=round(metrics.total_time_seconds, 1),
        avg_confidence=avg_confidence,
        total_cost=round(metrics.estimated_cost_usd, 4),
        cost_per_doc=cost_per_doc,
        doc_type_chart=doc_type_chart,
        time_chart=time_chart,
        documents=documents,
        samples=samples,
    )

    report_path.write_text(html, encoding="utf-8")
    logger.info("Generated benchmark report: %s", report_path)
    return report_path
