"""
extractors/medical_extractor.py
================================
Extracts structured fields from a medical record by passing the raw OCR text
and Comprehend Medical entities directly to Bedrock.

Output schema
-------------
{
  "hospitalName":   str,
  "doctorName":     str,
  "surgeryType":    str,
  "procedureDate":  str,   # YYYY-MM-DD when parseable, else empty string
  "diagnosis":      str,
  "medications":    list[str],
  "confidence":     float,  # mean Comprehend Medical entity score, or 0
  "purposeOfVisit": str,
}
"""

from __future__ import annotations

import json
import logging
from statistics import mean
from typing import Any

import bedrock_utils

logger = logging.getLogger(__name__)


def extract_medical_data(
    textract_result: dict[str, Any],
    comprehend_medical_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Parameters
    ----------
    textract_result           : output of textract_utils.extract_document()
    comprehend_medical_result : output of comprehend_medical_utils.analyze_medical_text()

    Returns
    -------
    extractedData dict ready for the review record.
    """
    raw_text = textract_result.get("raw_text", "")
    entities = comprehend_medical_result.get("entities", [])

    # Mean confidence from Comprehend Medical (0 when it detected nothing)
    scores = [e.get("score", 0.0) for e in entities]
    confidence = round(mean(scores), 4) if scores else 0.0

    # Compact entity summary for the prompt
    entities_summary = json.dumps(
        [
            {
                "text":     e["text"],
                "category": e["category"],
                "type":     e["type"],
                "traits":   e.get("traits", []),
            }
            for e in entities
        ],
        ensure_ascii=False,
    )

    prompt = (
        "You are a medical record parser. "
        "Using the raw medical record text and the Comprehend Medical entities below, "
        "extract the following fields and return ONLY a valid JSON object with exactly these 7 keys:\n\n"
        "  hospitalName   - full human-readable hospital name (NOT a machine ID like 'hospital_xxx_yyy')\n"
        "  doctorName     - consulting doctor's full name including title (e.g. 'Dr. Anand Pandey'). "
                           "Use only the name, do NOT include any extra words after it.\n"
        "  surgeryType    - procedure or surgery performed; empty string if none mentioned\n"
        "  procedureDate  - date of procedure in YYYY-MM-DD format; empty string if not found\n"
        "  diagnosis      - primary diagnosis or medical condition; empty string if not found\n"
        "  medications    - JSON array of medication strings (with dosage if available); empty array [] if none\n"
        "  purposeOfVisit - primary reason or complaint for this visit in 5-20 words; empty string if not found\n\n"
        "Rules:\n"
        "- Return ONLY the JSON object. No explanation, no markdown, no code fences.\n"
        "- hospitalName must be the printed name of the hospital, not an internal ID.\n"
        "- doctorName must be exactly 'Dr. FirstName LastName' - stop at the name, nothing after.\n\n"
        f"COMPREHEND MEDICAL ENTITIES:\n{entities_summary}\n\n"
        f"RAW MEDICAL RECORD TEXT:\n{raw_text[:5000]}"
    )

    fields = bedrock_utils.extract_structured_fields_medical(prompt)
    logger.info("Bedrock extracted fields (medical model): %s", fields)

    result = {
        "hospitalName":   str(fields.get("hospitalName")  or ""),
        "doctorName":     str(fields.get("doctorName")    or ""),
        "surgeryType":    str(fields.get("surgeryType")   or ""),
        "procedureDate":  str(fields.get("procedureDate") or ""),
        "diagnosis":      str(fields.get("diagnosis")     or ""),
        "medications":    fields.get("medications") if isinstance(fields.get("medications"), list) else [],
        "confidence":     confidence,
        "purposeOfVisit": str(fields.get("purposeOfVisit") or ""),
    }

    logger.info("Final extracted medical data: %s", result)
    return result
