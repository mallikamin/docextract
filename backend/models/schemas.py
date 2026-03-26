"""All Pydantic models for request/response/internal data."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# --- Enums ---

class DocumentType(str, Enum):
    BANK_STATEMENT = "bank_statement"
    INVOICE = "invoice"
    RECEIPT = "receipt"
    KYC_DOCUMENT = "kyc_document"
    UNKNOWN = "unknown"


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStage(str, Enum):
    CONVERTING = "converting"
    PREPROCESSING = "preprocessing"
    OCR = "ocr"
    CLASSIFYING = "classifying"
    EXTRACTING = "extracting"
    GENERATING_CSV = "generating_csv"
    GENERATING_REPORT = "generating_report"
    COMPLETED = "completed"


class CSVStrategy(str, Enum):
    SINGLE_ROW = "single_row"
    MULTI_ROW = "multi_row"


# --- Document extraction results ---

class ExtractionResult(BaseModel):
    filename: str
    doc_type: DocumentType = DocumentType.UNKNOWN
    classification_confidence: float = 0.0
    fields: Dict[str, Any] = Field(default_factory=dict)
    transactions: List[Dict[str, Any]] = Field(default_factory=list)
    line_items: List[Dict[str, Any]] = Field(default_factory=list)
    page_count: int = 0
    ocr_text: str = ""
    ocr_confidence: float = 0.0
    extraction_confidence: float = 0.0
    processing_time_ms: int = 0
    tokens_used: Dict[str, int] = Field(default_factory=dict)
    error: Optional[str] = None


# --- Job models ---

class DocumentStatus(BaseModel):
    filename: str
    doc_type: Optional[DocumentType] = None
    status: str = "pending"
    page_count: int = 0
    confidence: float = 0.0
    extraction_preview: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class JobMetrics(BaseModel):
    total_time_seconds: float = 0.0
    ocr_time_seconds: float = 0.0
    llm_time_seconds: float = 0.0
    tokens_used: Dict[str, int] = Field(default_factory=lambda: {"input": 0, "output": 0})
    estimated_cost_usd: float = 0.0


class Job(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    file_count: int = 0
    files_processed: int = 0
    current_file: Optional[str] = None
    current_stage: Optional[ProcessingStage] = None
    documents: List[DocumentStatus] = Field(default_factory=list)
    extractions: List[ExtractionResult] = Field(default_factory=list)
    error: Optional[str] = None
    csv_url: Optional[str] = None
    report_url: Optional[str] = None
    metrics: JobMetrics = Field(default_factory=JobMetrics)


# --- API response models ---

class UploadResponse(BaseModel):
    job_id: str
    status: str = "queued"
    file_count: int
    created_at: datetime
    stream_url: str


class HealthCheck(BaseModel):
    status: str
    checks: Dict[str, Any]
    timestamp: datetime


# --- CSV strategy mapping ---

DOC_TYPE_STRATEGY = {
    DocumentType.INVOICE: CSVStrategy.SINGLE_ROW,
    DocumentType.RECEIPT: CSVStrategy.SINGLE_ROW,
    DocumentType.KYC_DOCUMENT: CSVStrategy.SINGLE_ROW,
    DocumentType.BANK_STATEMENT: CSVStrategy.MULTI_ROW,
    DocumentType.UNKNOWN: CSVStrategy.SINGLE_ROW,
}
