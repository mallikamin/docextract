"""Structured data extraction using Claude Sonnet with tool_use.

Different tool schemas per document type enforce structured JSON output.
"""

import logging
from typing import Any, Dict, List, Optional

from backend.models.schemas import DocumentType
from backend.services.claude_client import ClaudeClient

logger = logging.getLogger(__name__)

# --- Tool schemas per document type ---

EXTRACTION_TOOLS = {
    DocumentType.INVOICE: {
        "name": "extract_invoice",
        "description": "Extract structured data from a financial invoice or bill.",
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor_name": {"type": "string", "description": "Company or vendor issuing the invoice"},
                "invoice_number": {"type": "string", "description": "Invoice or bill number"},
                "invoice_date": {"type": "string", "description": "Invoice date in YYYY-MM-DD format"},
                "due_date": {"type": "string", "description": "Payment due date in YYYY-MM-DD"},
                "currency": {"type": "string", "description": "Currency code (USD, EUR, GBP, PKR, etc.)"},
                "subtotal": {"type": "number", "description": "Subtotal before tax"},
                "tax": {"type": "number", "description": "Tax amount"},
                "total": {"type": "number", "description": "Total amount due"},
                "payment_terms": {"type": "string", "description": "Payment terms (Net 30, etc.)"},
                "bill_to": {"type": "string", "description": "Customer/recipient name or company"},
                "line_items": {
                    "type": "array",
                    "description": "Individual line items on the invoice",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "quantity": {"type": "number"},
                            "unit_price": {"type": "number"},
                            "amount": {"type": "number"},
                        },
                    },
                },
            },
            "required": ["vendor_name", "total", "currency"],
        },
    },
    DocumentType.BANK_STATEMENT: {
        "name": "extract_bank_statement",
        "description": "Extract structured data from a bank account statement.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bank_name": {"type": "string", "description": "Name of the bank"},
                "account_number": {"type": "string", "description": "Account number (may be partially masked)"},
                "account_holder": {"type": "string", "description": "Name of account holder"},
                "statement_period_start": {"type": "string", "description": "Statement start date YYYY-MM-DD"},
                "statement_period_end": {"type": "string", "description": "Statement end date YYYY-MM-DD"},
                "opening_balance": {"type": "number", "description": "Opening/beginning balance"},
                "closing_balance": {"type": "number", "description": "Closing/ending balance"},
                "currency": {"type": "string", "description": "Currency code"},
                "total_deposits": {"type": "number", "description": "Total credits/deposits"},
                "total_withdrawals": {"type": "number", "description": "Total debits/withdrawals"},
                "transactions": {
                    "type": "array",
                    "description": "List of individual transactions",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Transaction date YYYY-MM-DD"},
                            "description": {"type": "string", "description": "Transaction description"},
                            "reference": {"type": "string", "description": "Reference/check number"},
                            "debit": {"type": "number", "description": "Debit/withdrawal amount (0 if credit)"},
                            "credit": {"type": "number", "description": "Credit/deposit amount (0 if debit)"},
                            "balance": {"type": "number", "description": "Running balance after transaction"},
                        },
                    },
                },
            },
            "required": ["bank_name", "currency"],
        },
    },
    DocumentType.RECEIPT: {
        "name": "extract_receipt",
        "description": "Extract structured data from a payment receipt.",
        "input_schema": {
            "type": "object",
            "properties": {
                "merchant_name": {"type": "string", "description": "Store or merchant name"},
                "receipt_number": {"type": "string", "description": "Receipt or transaction number"},
                "date": {"type": "string", "description": "Receipt date YYYY-MM-DD"},
                "time": {"type": "string", "description": "Transaction time HH:MM"},
                "currency": {"type": "string", "description": "Currency code"},
                "subtotal": {"type": "number", "description": "Subtotal before tax"},
                "tax": {"type": "number", "description": "Tax amount"},
                "total": {"type": "number", "description": "Total paid"},
                "payment_method": {"type": "string", "description": "Cash, card, etc."},
                "items": {
                    "type": "array",
                    "description": "Purchased items",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "quantity": {"type": "number"},
                            "unit_price": {"type": "number"},
                            "amount": {"type": "number"},
                        },
                    },
                },
            },
            "required": ["merchant_name", "total", "currency"],
        },
    },
    DocumentType.KYC_DOCUMENT: {
        "name": "extract_kyc_document",
        "description": "Extract structured data from a KYC/identity document.",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_type": {"type": "string", "description": "Type: passport, drivers_license, national_id, utility_bill, etc."},
                "document_id": {"type": "string", "description": "Document/ID number"},
                "full_name": {"type": "string", "description": "Full name as shown on document"},
                "date_of_birth": {"type": "string", "description": "Date of birth YYYY-MM-DD"},
                "nationality": {"type": "string", "description": "Nationality or country"},
                "address": {"type": "string", "description": "Address on document"},
                "issue_date": {"type": "string", "description": "Issue date YYYY-MM-DD"},
                "expiry_date": {"type": "string", "description": "Expiry date YYYY-MM-DD"},
                "issuing_authority": {"type": "string", "description": "Issuing authority/organization"},
                "gender": {"type": "string", "description": "Gender if shown"},
            },
            "required": ["full_name"],
        },
    },
}

# Fallback for unknown documents
UNKNOWN_TOOL = {
    "name": "extract_document",
    "description": "Extract any structured data found in the document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "document_type": {"type": "string", "description": "Best guess at document type"},
            "title": {"type": "string", "description": "Document title or heading"},
            "date": {"type": "string", "description": "Primary date found"},
            "amounts": {
                "type": "array",
                "description": "All monetary amounts found",
                "items": {"type": "object", "properties": {"label": {"type": "string"}, "amount": {"type": "number"}, "currency": {"type": "string"}}},
            },
            "entities": {
                "type": "array",
                "description": "Names, organizations, IDs found",
                "items": {"type": "object", "properties": {"label": {"type": "string"}, "value": {"type": "string"}}},
            },
            "key_fields": {
                "type": "object",
                "description": "Any other key-value pairs extracted",
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["document_type"],
    },
}


EXTRACTION_SYSTEM = """You are a financial document data extraction specialist.
Extract ALL structured data from the document text below.
Be precise with numbers, dates, and amounts.
Use ISO 8601 dates (YYYY-MM-DD) wherever possible.
For amounts, use numeric values without currency symbols.
If a field is not found in the document, omit it from the output."""


def extract_data(
    ocr_text: str,
    doc_type: DocumentType,
    client: ClaudeClient,
) -> Dict[str, Any]:
    """Extract structured data from OCR text using Claude Sonnet with tool_use.

    Returns the tool_input dict (structured extraction) or empty dict on failure.
    """
    tool = EXTRACTION_TOOLS.get(doc_type, UNKNOWN_TOOL)

    prompt = f"""Extract all structured data from this {doc_type.value} document.

Document text:
---
{ocr_text[:6000]}
---

Use the provided tool to return the extracted data."""

    result = client.call_sonnet(
        prompt=prompt,
        system=EXTRACTION_SYSTEM,
        tools=[tool],
    )

    if not result["success"]:
        logger.error("Extraction failed: %s", result.get("error"))
        return {"error": result.get("error"), "_usage": result.get("usage", {})}

    extracted = result.get("tool_input") or {}
    extracted["_usage"] = result.get("usage", {})
    extracted["_duration_ms"] = result.get("duration_ms", 0)

    logger.info(
        "Extracted %d fields from %s document",
        len([k for k in extracted if not k.startswith("_")]),
        doc_type.value,
    )
    return extracted
