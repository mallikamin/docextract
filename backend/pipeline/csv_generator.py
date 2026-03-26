"""Smart CSV generation with adaptive row strategy.

Produces two CSV files:
  - summary.csv: One row per document (manager view)
  - transactions.csv: One row per transaction (auditor view)
"""

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List

from backend.models.schemas import (
    CSVStrategy, DOC_TYPE_STRATEGY, DocumentType, ExtractionResult,
)

logger = logging.getLogger(__name__)

# Column definitions
SUMMARY_COLUMNS = [
    "source_file", "doc_type", "entity_name", "document_id",
    "date", "currency", "total_amount", "confidence", "fields_extracted",
]

TRANSACTION_COLUMNS = [
    "source_file", "doc_type", "account_or_vendor", "period",
    "transaction_date", "description", "reference",
    "debit", "credit", "balance",
]


def generate_csv(extractions: List[ExtractionResult], output_dir: Path) -> Dict[str, Path]:
    """Generate smart CSV files from extraction results.

    Returns dict with paths: {"summary": Path, "transactions": Path}
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.csv"
    transactions_path = output_dir / "transactions.csv"

    summary_rows: List[Dict[str, Any]] = []
    transaction_rows: List[Dict[str, Any]] = []

    for ext in extractions:
        if ext.error:
            summary_rows.append({
                "source_file": ext.filename,
                "doc_type": ext.doc_type.value,
                "entity_name": "ERROR",
                "document_id": "",
                "date": "",
                "currency": "",
                "total_amount": "",
                "confidence": f"{ext.extraction_confidence:.0%}",
                "fields_extracted": 0,
            })
            continue

        fields = ext.fields
        strategy = DOC_TYPE_STRATEGY.get(ext.doc_type, CSVStrategy.SINGLE_ROW)

        # Build summary row (all doc types get one)
        summary_row = _build_summary_row(ext)
        summary_rows.append(summary_row)

        # Build transaction rows for multi-row types
        if strategy == CSVStrategy.MULTI_ROW:
            txns = _build_transaction_rows(ext)
            transaction_rows.extend(txns)

        # Invoices with line_items also go to transactions
        if ext.doc_type == DocumentType.INVOICE and ext.line_items:
            items = _build_line_item_rows(ext)
            transaction_rows.extend(items)

    # Write CSVs
    _write_csv(summary_path, SUMMARY_COLUMNS, summary_rows)
    result = {"summary": summary_path}

    if transaction_rows:
        _write_csv(transactions_path, TRANSACTION_COLUMNS, transaction_rows)
        result["transactions"] = transactions_path

    logger.info(
        "Generated CSV: %d summary rows, %d transaction rows",
        len(summary_rows), len(transaction_rows),
    )
    return result


def _build_summary_row(ext: ExtractionResult) -> Dict[str, Any]:
    """Build a summary row from any extraction result."""
    f = ext.fields
    entity = (
        f.get("vendor_name") or f.get("bank_name") or
        f.get("merchant_name") or f.get("full_name") or
        f.get("title") or ""
    )
    doc_id = (
        f.get("invoice_number") or f.get("account_number") or
        f.get("receipt_number") or f.get("document_id") or ""
    )
    date = (
        f.get("invoice_date") or f.get("date") or
        f.get("statement_period_end") or f.get("issue_date") or ""
    )
    currency = f.get("currency", "")
    total = (
        f.get("total") or f.get("closing_balance") or
        f.get("subtotal") or ""
    )
    field_count = len([k for k in f if not k.startswith("_")])

    return {
        "source_file": ext.filename,
        "doc_type": ext.doc_type.value,
        "entity_name": entity,
        "document_id": doc_id,
        "date": date,
        "currency": currency,
        "total_amount": total,
        "confidence": f"{ext.extraction_confidence:.0%}",
        "fields_extracted": field_count,
    }


def _build_transaction_rows(ext: ExtractionResult) -> List[Dict[str, Any]]:
    """Build transaction rows from bank statement transactions."""
    rows = []
    f = ext.fields
    account = f.get("account_number", "")
    bank = f.get("bank_name", "")
    period = f"{f.get('statement_period_start', '')} to {f.get('statement_period_end', '')}"

    for txn in ext.transactions:
        rows.append({
            "source_file": ext.filename,
            "doc_type": ext.doc_type.value,
            "account_or_vendor": f"{bank} - {account}" if bank else account,
            "period": period,
            "transaction_date": txn.get("date", ""),
            "description": txn.get("description", ""),
            "reference": txn.get("reference", ""),
            "debit": txn.get("debit", ""),
            "credit": txn.get("credit", ""),
            "balance": txn.get("balance", ""),
        })
    return rows


def _build_line_item_rows(ext: ExtractionResult) -> List[Dict[str, Any]]:
    """Build transaction rows from invoice line items."""
    rows = []
    f = ext.fields
    vendor = f.get("vendor_name", "")

    for item in ext.line_items:
        rows.append({
            "source_file": ext.filename,
            "doc_type": ext.doc_type.value,
            "account_or_vendor": vendor,
            "period": f.get("invoice_date", ""),
            "transaction_date": f.get("invoice_date", ""),
            "description": item.get("description", ""),
            "reference": f.get("invoice_number", ""),
            "debit": item.get("amount", ""),
            "credit": "",
            "balance": "",
        })
    return rows


def _write_csv(path: Path, columns: List[str], rows: List[Dict[str, Any]]):
    """Write rows to a CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
