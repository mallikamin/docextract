"""Pipeline orchestrator. Runs each stage sequentially per document, emits SSE events."""

import io
import logging
import time
from pathlib import Path
from typing import List

from backend.config import settings
from backend.models.schemas import (
    DocumentStatus, DocumentType, ExtractionResult,
    JobMetrics, JobStatus, ProcessingStage,
)
from backend.pipeline.classifier import classify_document
from backend.pipeline.csv_generator import generate_csv
from backend.pipeline.extractor import extract_data
from backend.pipeline.report_generator import generate_report
from backend.pipeline.ocr_engine import OCREngine
from backend.pipeline.pdf_converter import PDFConverter
from backend.pipeline.preprocessor import ImagePreprocessor
from backend.services import event_bus
from backend.services.claude_client import ClaudeClient
from backend.services.job_manager import get_job, get_job_dir, update_job

logger = logging.getLogger(__name__)


async def process_job(job_id: str):
    """Run the full extraction pipeline for a job."""
    job = get_job(job_id)
    if not job:
        logger.error("Job %s not found", job_id)
        return

    job.status = JobStatus.PROCESSING
    update_job(job)

    job_dir = get_job_dir(job_id)
    start_time = time.monotonic()
    ocr_time = 0.0
    llm_time = 0.0

    # Initialize components
    converter = PDFConverter()
    preprocessor = ImagePreprocessor({
        "deskew": settings.preprocessing_deskew,
        "denoise": settings.preprocessing_denoise,
        "enhance_contrast": settings.preprocessing_contrast,
        "binarize": settings.preprocessing_binarize,
    })
    ocr = OCREngine(
        languages=settings.ocr_languages.split(","),
        min_confidence=settings.ocr_min_confidence,
    )

    # Initialize Claude client
    try:
        client = ClaudeClient(
            api_key=settings.anthropic_api_key,
            haiku_model=settings.haiku_model,
            sonnet_model=settings.sonnet_model,
        )
    except RuntimeError as e:
        job.status = JobStatus.FAILED
        job.error = str(e)
        update_job(job)
        await event_bus.publish(job_id, "error", {"message": str(e)})
        return

    # Get input PDFs
    input_dir = job_dir / "input"
    pdf_files = sorted(input_dir.glob("*.pdf"))

    extractions: List[ExtractionResult] = []

    for idx, pdf_path in enumerate(pdf_files):
        filename = pdf_path.name
        job.current_file = filename
        job.current_stage = ProcessingStage.CONVERTING
        update_job(job)

        extraction = ExtractionResult(filename=filename)
        doc_start = time.monotonic()

        try:
            # Stage 1: PDF to images
            await event_bus.publish(job_id, "status", {
                "status": "processing", "current_file": filename,
                "current_stage": "converting", "progress_pct": _pct(idx, 0, len(pdf_files)),
            })
            pages = converter.convert(
                str(pdf_path), dpi=settings.ocr_dpi,
                output_dir=job_dir / "images",
            )
            extraction.page_count = len(pages)

            # Stage 2: Preprocess each page
            job.current_stage = ProcessingStage.PREPROCESSING
            update_job(job)
            await event_bus.publish(job_id, "status", {
                "status": "processing", "current_file": filename,
                "current_stage": "preprocessing", "progress_pct": _pct(idx, 1, len(pdf_files)),
            })

            preprocessed_images = []
            for page_num, img in pages:
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                processed_bytes = preprocessor.process(buf.getvalue())
                preprocessed_images.append((page_num, processed_bytes))

                # Save preprocessed
                out_path = job_dir / "preprocessed" / f"{pdf_path.stem}_page_{page_num:03d}.png"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(processed_bytes)

            # Stage 3: OCR
            job.current_stage = ProcessingStage.OCR
            update_job(job)
            await event_bus.publish(job_id, "status", {
                "status": "processing", "current_file": filename,
                "current_stage": "ocr", "progress_pct": _pct(idx, 2, len(pdf_files)),
            })

            ocr_start = time.monotonic()
            all_text_parts = []
            total_confidence = 0.0
            for page_num, img_bytes in preprocessed_images:
                result = ocr.extract_text(img_bytes)
                all_text_parts.append(result.get("text", ""))
                total_confidence += result.get("confidence", 0.0)

            full_text = "\n\n--- Page Break ---\n\n".join(all_text_parts)
            extraction.ocr_text = full_text
            extraction.ocr_confidence = total_confidence / max(len(preprocessed_images), 1)
            ocr_time += time.monotonic() - ocr_start

            # Save OCR text
            ocr_path = job_dir / "ocr" / f"{pdf_path.stem}.txt"
            ocr_path.write_text(full_text, encoding="utf-8")

            # Stage 4: Classification
            job.current_stage = ProcessingStage.CLASSIFYING
            update_job(job)
            await event_bus.publish(job_id, "status", {
                "status": "processing", "current_file": filename,
                "current_stage": "classifying", "progress_pct": _pct(idx, 3, len(pdf_files)),
            })

            llm_start = time.monotonic()
            classification = classify_document(full_text, client)
            extraction.doc_type = classification["doc_type"]
            extraction.classification_confidence = classification["confidence"]

            await event_bus.publish(job_id, "classification", {
                "filename": filename,
                "doc_type": extraction.doc_type.value,
                "confidence": extraction.classification_confidence,
            })

            # Stage 5: Extraction
            job.current_stage = ProcessingStage.EXTRACTING
            update_job(job)
            await event_bus.publish(job_id, "status", {
                "status": "processing", "current_file": filename,
                "current_stage": "extracting", "progress_pct": _pct(idx, 4, len(pdf_files)),
            })

            extracted = extract_data(full_text, extraction.doc_type, client)
            llm_time += time.monotonic() - llm_start

            # Separate transactions/line_items from fields
            usage = extracted.pop("_usage", {})
            duration = extracted.pop("_duration_ms", 0)
            transactions = extracted.pop("transactions", [])
            line_items = extracted.pop("line_items", extracted.pop("items", []))
            error = extracted.pop("error", None)

            extraction.fields = extracted
            extraction.transactions = transactions
            extraction.line_items = line_items
            extraction.tokens_used = usage
            extraction.extraction_confidence = extraction.classification_confidence
            extraction.processing_time_ms = int((time.monotonic() - doc_start) * 1000)

            if error:
                extraction.error = error

            # Save extraction JSON
            import json
            ext_path = job_dir / "extraction" / f"{pdf_path.stem}.json"
            ext_path.write_text(json.dumps(extracted, indent=2, default=str), encoding="utf-8")

            # Build preview for SSE
            preview = {k: v for k, v in list(extracted.items())[:5] if not k.startswith("_")}
            await event_bus.publish(job_id, "extraction", {
                "filename": filename,
                "doc_type": extraction.doc_type.value,
                "fields_extracted": len([k for k in extracted if not k.startswith("_")]),
                "preview": preview,
            })

        except Exception as e:
            logger.error("Failed processing %s: %s", filename, e, exc_info=True)
            extraction.error = str(e)
            await event_bus.publish(job_id, "error", {
                "message": f"Error processing {filename}: {e}",
                "filename": filename,
                "recoverable": True,
            })

        extractions.append(extraction)

        # Update job progress
        job.files_processed = idx + 1
        job.documents.append(DocumentStatus(
            filename=filename,
            doc_type=extraction.doc_type,
            status="completed" if not extraction.error else "failed",
            page_count=extraction.page_count,
            confidence=extraction.classification_confidence,
            extraction_preview={k: v for k, v in list(extraction.fields.items())[:5]},
            error=extraction.error,
        ))
        update_job(job)

        await event_bus.publish(job_id, "file_completed", {
            "filename": filename,
            "files_processed": job.files_processed,
            "file_count": job.file_count,
        })

    # Stage 6: Generate CSV
    job.current_stage = ProcessingStage.GENERATING_CSV
    update_job(job)
    await event_bus.publish(job_id, "status", {
        "status": "processing", "current_file": None,
        "current_stage": "generating_csv", "progress_pct": 90,
    })

    job.extractions = extractions
    output_dir = job_dir / "output"
    csv_paths = generate_csv(extractions, output_dir)

    # Stage 7: Generate report
    job.current_stage = ProcessingStage.GENERATING_REPORT
    update_job(job)
    await event_bus.publish(job_id, "status", {
        "status": "processing", "current_file": None,
        "current_stage": "generating_report", "progress_pct": 95,
    })

    # Calculate metrics
    total_time = time.monotonic() - start_time
    total_input = sum(e.tokens_used.get("input", 0) for e in extractions)
    total_output = sum(e.tokens_used.get("output", 0) for e in extractions)

    job.metrics = JobMetrics(
        total_time_seconds=round(total_time, 1),
        ocr_time_seconds=round(ocr_time, 1),
        llm_time_seconds=round(llm_time, 1),
        tokens_used={"input": total_input, "output": total_output},
        estimated_cost_usd=round(client.total_cost_usd, 4),
    )

    # Generate benchmark report
    try:
        generate_report(job_id, extractions, job.metrics, output_dir)
    except Exception as e:
        logger.error("Report generation failed: %s", e)

    # Finalize job
    from datetime import datetime
    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.utcnow()
    job.current_stage = ProcessingStage.COMPLETED
    job.current_file = None
    job.csv_url = f"/api/jobs/{job_id}/download/csv"
    job.report_url = f"/api/jobs/{job_id}/download/report"
    update_job(job)

    await event_bus.publish(job_id, "completed", {
        "job_id": job_id,
        "csv_url": job.csv_url,
        "report_url": job.report_url,
        "metrics": job.metrics.model_dump(),
    })

    logger.info(
        "Job %s completed: %d files, %.1fs, $%.4f",
        job_id, len(extractions), total_time, client.total_cost_usd,
    )


def _pct(file_idx: int, stage: int, total_files: int) -> int:
    """Calculate overall progress percentage."""
    stages_per_file = 5
    total_stages = total_files * stages_per_file + 1  # +1 for CSV gen
    current = file_idx * stages_per_file + stage
    return min(int((current / total_stages) * 100), 99)
