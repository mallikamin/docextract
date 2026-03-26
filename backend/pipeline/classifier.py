"""Document classification using Claude Haiku.

Takes OCR text, returns document type + confidence.
"""

import logging
from backend.models.schemas import DocumentType
from backend.services.claude_client import ClaudeClient
from backend.utils.helpers import extract_json

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """Classify this financial document into exactly ONE category based on the text below.

Categories:
- bank_statement: Bank account statements with transactions, balances, account numbers
- invoice: Bills, invoices with vendor name, line items, totals, due dates
- receipt: Payment receipts, purchase receipts with merchant, date, total
- kyc_document: Identity documents, utility bills for KYC, proof of address
- unknown: Cannot determine the document type

Respond with ONLY this JSON (no other text):
{{"doc_type": "<category>", "confidence": <0.0-1.0>}}

Document text (first 2000 chars):
---
{text}
---"""


def classify_document(ocr_text: str, client: ClaudeClient) -> dict:
    """Classify a document using Claude Haiku.

    Returns: {"doc_type": DocumentType, "confidence": float}
    """
    # Only send first 2000 chars — enough for classification
    truncated = ocr_text[:2000]

    result = client.call_haiku(
        prompt=CLASSIFICATION_PROMPT.format(text=truncated),
        system="You are a financial document classifier. Respond with only valid JSON.",
    )

    if not result["success"]:
        logger.error("Classification failed: %s", result.get("error"))
        return {"doc_type": DocumentType.UNKNOWN, "confidence": 0.0}

    try:
        parsed = extract_json(result["text"])
        doc_type_str = parsed.get("doc_type", "unknown")
        confidence = float(parsed.get("confidence", 0.0))

        # Map to enum
        try:
            doc_type = DocumentType(doc_type_str)
        except ValueError:
            doc_type = DocumentType.UNKNOWN

        return {"doc_type": doc_type, "confidence": confidence}

    except Exception as e:
        logger.error("Failed to parse classification: %s", e)
        return {"doc_type": DocumentType.UNKNOWN, "confidence": 0.0}
