"""Utility functions: JSON extraction, date normalization."""

import json
import re
from typing import Optional


def extract_json(text: str) -> dict:
    """Extract a JSON object from LLM output text.

    Handles markdown fences, preamble text, trailing garbage.
    Raises json.JSONDecodeError if no valid JSON found.
    """
    # 1. Direct parse (fast path)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Find first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError("No valid JSON found in LLM output", text, 0)


def normalize_currency(value: str) -> Optional[float]:
    """Parse a currency string to float. Handles $, commas, spaces."""
    if not value:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", str(value))
    try:
        return round(float(cleaned), 2)
    except (ValueError, TypeError):
        return None


def normalize_date(value: str) -> Optional[str]:
    """Try to normalize a date string to ISO 8601 (YYYY-MM-DD)."""
    if not value:
        return None
    from dateutil import parser as dateparser
    try:
        dt = dateparser.parse(value, dayfirst=False)
        return dt.strftime("%Y-%m-%d") if dt else None
    except (ValueError, TypeError):
        return None
