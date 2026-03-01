"""
extractors/claim_extractor.py
=============================
Maps Textract + Comprehend output for an insuranceClaim document into the
claim{} sub-object expected by the Review DynamoDB record.

Output schema
-------------
{
  "claimId":                  str,   # e.g. "CLM-528527"
  "claimAmountApproved":      str,   # e.g. "₹65583"
  "remainingAmountToBePaid":  str,   # e.g. "₹43016"  (patient's share)
}
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_CLAIM_NO_RE = re.compile(r"CLM[-–\s]?\d{4,}", re.IGNORECASE)
_AMOUNT_RE   = re.compile(r"[₹Rs\.]+\s*([\d,]+(?:\.\d+)?)")
_DIGIT_RE    = re.compile(r"[\d,]+")


def extract_claim(
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
    claim dict ready for the review record.
    """
    raw_text    = textract_result.get("raw_text", "")
    key_values  = textract_result.get("key_values", {})
    key_phrases = comprehend_result.get("key_phrases", [])

    claim_id           = _extract_claim_id(raw_text, key_values, key_phrases)
    amounts            = _extract_all_amounts(raw_text, key_values, key_phrases)
    approved, remaining = _assign_amounts(raw_text, key_values, amounts)

    claim = {
        "claimId":                 claim_id,
        "claimAmountApproved":     approved,
        "remainingAmountToBePaid": remaining,
    }

    logger.info("Extracted claim: %s", claim)
    return claim


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_claim_id(
    raw_text: str,
    key_values: dict[str, str],
    key_phrases: list[str],
) -> str:
    # 1. Key-value pairs from Textract
    for kv_key, kv_val in key_values.items():
        if re.search(r"claim\s*(no|number|id|#)", kv_key, re.IGNORECASE):
            candidate = kv_val.strip()
            if candidate:
                return _normalise_claim_id(candidate)

    # 2. Regex on raw text
    m = _CLAIM_NO_RE.search(raw_text)
    if m:
        return _normalise_claim_id(m.group())

    # 3. Comprehend key phrases
    for phrase in key_phrases:
        m2 = _CLAIM_NO_RE.search(phrase)
        if m2:
            return _normalise_claim_id(m2.group())

    return ""


def _normalise_claim_id(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    return f"CLM-{digits}" if digits else raw.strip().upper()


def _extract_all_amounts(
    raw_text: str,
    key_values: dict[str, str],
    key_phrases: list[str],
) -> list[float]:
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
    return sorted(found, reverse=True)


def _assign_amounts(
    raw_text: str,
    key_values: dict[str, str],
    amounts: list[float],
) -> tuple[str, str]:
    """
    Return (claimAmountApproved, remainingAmountToBePaid).

    Strategy:
    1. Look for labelled KV pairs ("approved", "settled", "balance", "remaining").
    2. Fall back to largest = approved, smallest = remaining.
    """
    approved  = ""
    remaining = ""

    _approve_re  = re.compile(r"approved|settled|sanctioned|covered", re.IGNORECASE)
    _balance_re  = re.compile(r"balance|remaining|due|payable|patient", re.IGNORECASE)

    for kv_key, kv_val in key_values.items():
        m = _DIGIT_RE.search(kv_val.replace(",", ""))
        if not m:
            continue
        val_str = f"₹{int(float(m.group()))}"
        if _approve_re.search(kv_key) and not approved:
            approved = val_str
        if _balance_re.search(kv_key) and not remaining:
            remaining = val_str

    # Fallback: largest → approved, smallest → remaining
    if not approved and amounts:
        approved = f"₹{int(amounts[0])}"
    if not remaining and len(amounts) >= 2:
        remaining = f"₹{int(amounts[-1])}"
    elif not remaining and amounts:
        remaining = approved  # single amount; patient pays full

    return approved, remaining
