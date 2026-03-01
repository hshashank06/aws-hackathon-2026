"""
extractors/bill_extractor.py
============================
Maps Textract + Comprehend output for a hospitalBill document into the
payment{} sub-object expected by the Review DynamoDB record.

Output schema
-------------
{
  "billNo":          str,   # e.g. "BILL-79780"
  "totalBillAmount": str,   # e.g. "₹108599"
  "amountToBePayed": str,   # e.g. "₹34956"  (patient's share)
}
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Regex patterns
_BILL_NO_RE   = re.compile(r"BILL[-–\s]?\d{4,}", re.IGNORECASE)
_AMOUNT_RE    = re.compile(r"[₹Rs\.]+\s*([\d,]+(?:\.\d+)?)")   # ₹ or Rs. amounts
_DIGIT_RE     = re.compile(r"[\d,]+")


def extract_payment(
    textract_result: dict[str, Any],
    comprehend_result: dict[str, Any],
) -> dict[str, str]:
    """
    Parameters
    ----------
    textract_result  : output of textract_utils.extract_document()
    comprehend_result: output of comprehend_utils.analyze_text()

    Returns
    -------
    payment dict ready for the review record.
    """
    raw_text    = textract_result.get("raw_text", "")
    key_values  = textract_result.get("key_values", {})
    key_phrases = comprehend_result.get("key_phrases", [])
    entities    = comprehend_result.get("entities", [])

    # ------------------------------------------------------------------ Bill No
    bill_no = _extract_bill_no(raw_text, key_values, key_phrases)

    # ------------------------------------------------------------------ Amounts
    amounts = _extract_all_amounts(raw_text, key_values, key_phrases, entities)

    total_bill    = ""
    amount_to_pay = ""

    if amounts:
        amounts_sorted = sorted(amounts, reverse=True)
        total_bill    = f"₹{_fmt(amounts_sorted[0])}"
        # patient payable is usually the smallest non-zero distinct amount
        if len(amounts_sorted) >= 2:
            # look for an amount explicitly labelled as "due", "payable", "balance"
            amount_to_pay = _find_labelled_amount(raw_text, key_values, amounts_sorted) or f"₹{_fmt(amounts_sorted[-1])}"
        else:
            amount_to_pay = total_bill  # only one amount found

    payment = {
        "billNo":          bill_no,
        "totalBillAmount": total_bill,
        "amountToBePayed": amount_to_pay,
    }

    logger.info("Extracted payment: %s", payment)
    return payment


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_bill_no(
    raw_text: str,
    key_values: dict[str, str],
    key_phrases: list[str],
) -> str:
    # 1. From Textract key-value pairs (most reliable)
    for kv_key, kv_val in key_values.items():
        if re.search(r"bill\s*(no|number|#|id)", kv_key, re.IGNORECASE):
            candidate = kv_val.strip()
            if candidate:
                return _normalise_bill_no(candidate)

    # 2. From raw text using regex
    match = _BILL_NO_RE.search(raw_text)
    if match:
        return _normalise_bill_no(match.group())

    # 3. From Comprehend key phrases
    for phrase in key_phrases:
        m = _BILL_NO_RE.search(phrase)
        if m:
            return _normalise_bill_no(m.group())

    return ""


def _normalise_bill_no(raw: str) -> str:
    """Ensure format is BILL-NNNNN"""
    digits = re.sub(r"\D", "", raw)
    return f"BILL-{digits}" if digits else raw.strip().upper()


def _extract_all_amounts(
    raw_text: str,
    key_values: dict[str, str],
    key_phrases: list[str],
    entities: list[dict],
) -> list[float]:
    """Collect all ₹ amounts from every source and return unique sorted list."""
    found: set[float] = set()

    for source in [raw_text, *key_values.values(), *key_phrases]:
        for m in _AMOUNT_RE.finditer(str(source)):
            val_str = m.group(1).replace(",", "")
            try:
                val = float(val_str)
                if val > 0:
                    found.add(val)
            except ValueError:
                pass

    # Also check QUANTITY entities from Comprehend
    for ent in entities:
        if ent.get("type") == "QUANTITY":
            m = _DIGIT_RE.search(ent["text"].replace(",", ""))
            if m:
                try:
                    found.add(float(m.group()))
                except ValueError:
                    pass

    return sorted(found, reverse=True)


def _find_labelled_amount(
    raw_text: str,
    key_values: dict[str, str],
    amounts: list[float],
) -> str:
    """
    Look for key phrases like "Balance Due", "Net Payable", "Amount Due"
    followed by an amount. Returns formatted ₹ string or "".
    """
    payable_re = re.compile(
        r"(balance\s*due|net\s*payable|amount\s*due|patient\s*pays|you\s*owe)"
        r"[\s:₹Rs\.]*"
        r"([\d,]+)",
        re.IGNORECASE,
    )
    # Search key values first
    for kv_key, kv_val in key_values.items():
        if re.search(r"balance|payable|due|patient", kv_key, re.IGNORECASE):
            m = _DIGIT_RE.search(kv_val.replace(",", ""))
            if m:
                return f"₹{_fmt(float(m.group()))}"

    # Search raw text
    for m in payable_re.finditer(raw_text):
        return f"₹{_fmt(float(m.group(2).replace(',', '')))}"

    return ""


def _fmt(amount: float) -> str:
    """Format float as integer string (no trailing .0)."""
    return str(int(amount))
