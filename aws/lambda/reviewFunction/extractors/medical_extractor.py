"""
extractors/medical_extractor.py
================================
Maps Amazon Comprehend Medical entity output into the extractedData{}
sub-object expected by the Review DynamoDB record.

Output schema
-------------
{
  "hospitalName":  str,
  "doctorName":    str,
  "surgeryType":   str,
  "procedureDate": str,   # YYYY-MM-DD when parseable
  "diagnosis":     str,
  "medications":   list[str],
  "confidence":    float,  # mean entity score
}
"""

from __future__ import annotations

import logging
import re
from statistics import mean
from typing import Any

logger = logging.getLogger(__name__)

# ISO date normalisation
_DATE_PATTERNS = [
    re.compile(r"(\d{4})-(\d{2})-(\d{2})"),                      # 2025-08-18
    re.compile(r"(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})"),          # 18/08/2025
    re.compile(r"(\d{1,2})\s+(\w+)\s+(\d{4})", re.IGNORECASE),   # 18 August 2025
]
_MONTH_MAP = {
    "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
    "jan":1,"feb":2,"mar":3,"apr":4,"jun":6,"jul":7,"aug":8,
    "sep":9,"oct":10,"nov":11,"dec":12,
}


def extract_medical_data(
    textract_result: dict[str, Any],
    comprehend_medical_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Parameters
    ----------
    textract_result            : output of textract_utils.extract_document()
    comprehend_medical_result  : output of comprehend_medical_utils.analyze_medical_text()

    Returns
    -------
    extractedData dict ready for the review record.
    """
    entities    = comprehend_medical_result.get("entities", [])
    key_values  = textract_result.get("key_values", {})
    raw_text    = textract_result.get("raw_text", "")

    hospital_name  = ""
    doctor_name    = ""
    surgery_type   = ""
    procedure_date = ""
    diagnosis_parts: list[str] = []
    medications:     list[str] = []
    scores:          list[float] = []

    for ent in entities:
        text     = ent["text"]
        category = ent["category"]
        typ      = ent["type"]
        traits   = ent.get("traits", [])
        score    = ent.get("score", 0.0)
        scores.append(score)

        if category == "MEDICATION" and text not in medications:
            # Enrich with dosage attributes if available
            med_str = text
            for attr in ent.get("attributes", []):
                if attr["type"] in ("DOSAGE", "FORM", "FREQUENCY"):
                    med_str += f" {attr['text']}"
            medications.append(med_str.strip())

        elif category == "MEDICAL_CONDITION":
            if "DIAGNOSIS" in traits or typ == "DX_NAME":
                if text not in diagnosis_parts:
                    diagnosis_parts.append(text)

        elif category == "PROCEDURE":
            if not surgery_type or score > 0.85:
                surgery_type = text

        elif category == "TIME_EXPRESSION" or (category == "PROTECTED_HEALTH_INFORMATION" and typ == "DATE"):
            if "PROCEDURE_DATE" in traits or not procedure_date:
                normalised = _to_iso_date(text)
                if normalised:
                    procedure_date = normalised

        elif category == "PROTECTED_HEALTH_INFORMATION":
            if typ == "NAME" and not doctor_name:
                doctor_name = text
            elif typ in ("ADDRESS", "HOSPITAL") and not hospital_name:
                hospital_name = text

    # ------------------------------------------------------------------ Fallbacks from Textract KV
    if not hospital_name:
        for kv_key, kv_val in key_values.items():
            if re.search(r"hospital|clinic|facility", kv_key, re.IGNORECASE) and kv_val.strip():
                hospital_name = kv_val.strip()
                break

    if not doctor_name:
        # First occurrence of "Dr." in raw text
        m = re.search(r"Dr\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", raw_text)
        if m:
            doctor_name = f"Dr. {m.group(1)}"

    if not procedure_date:
        for kv_key, kv_val in key_values.items():
            if re.search(r"date|procedure|admission|discharge", kv_key, re.IGNORECASE):
                d = _to_iso_date(kv_val)
                if d:
                    procedure_date = d
                    break

    diagnosis = "; ".join(diagnosis_parts) if diagnosis_parts else ""
    confidence = round(mean(scores), 4) if scores else 0.0

    result = {
        "hospitalName":  hospital_name,
        "doctorName":    doctor_name,
        "surgeryType":   surgery_type,
        "procedureDate": procedure_date,
        "diagnosis":     diagnosis,
        "medications":   medications,
        "confidence":    confidence,
    }

    logger.info("Extracted medical data: %s", result)
    return result


# ---------------------------------------------------------------------------
# Date normalisation
# ---------------------------------------------------------------------------

def _to_iso_date(text: str) -> str:
    """Try to convert a date string to YYYY-MM-DD. Returns "" on failure."""
    text = text.strip()

    # Already ISO
    m = _DATE_PATTERNS[0].search(text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    m = _DATE_PATTERNS[1].search(text)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"

    # DD Month YYYY
    m = _DATE_PATTERNS[2].search(text)
    if m:
        day   = m.group(1).zfill(2)
        month = _MONTH_MAP.get(m.group(2).lower(), 0)
        year  = m.group(3)
        if month:
            return f"{year}-{str(month).zfill(2)}-{day}"

    return ""
