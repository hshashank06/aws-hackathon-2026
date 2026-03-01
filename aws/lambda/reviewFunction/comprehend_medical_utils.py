"""
comprehend_medical_utils.py
===========================
Wraps Amazon Comprehend Medical DetectEntitiesV2 to extract clinical entities
from medical record text (output of Textract).

Public API
----------
  analyze_medical_text(text)
      → {
            "entities": list[{
                "text":     str,
                "category": str,   # e.g. MEDICATION, MEDICAL_CONDITION …
                "type":     str,   # e.g. DX_NAME, GENERIC_NAME …
                "traits":   list[str],
                "score":    float,
            }]
         }
"""

from __future__ import annotations

import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)

AWS_REGION: str = os.environ.get("AWS_REGION", "us-east-1")

_comprehend_medical = boto3.client("comprehendmedical", region_name=AWS_REGION)

# Comprehend Medical text limit is 20,000 characters
_MAX_CHARS = 19_000


def analyze_medical_text(text: str) -> dict[str, Any]:
    """
    Run Comprehend Medical DetectEntitiesV2 on the supplied text.

    Returns
    -------
    {
      "entities": [
        {
          "text":     str,
          "category": str,
          "type":     str,
          "traits":   list[str],   # e.g. ["DIAGNOSIS", "PROCEDURE_DATE"]
          "score":    float,
          "attributes": list[{     # related attributes (e.g. dosage for medication)
              "text":  str,
              "type":  str,
              "score": float,
          }]
        }
      ]
    }
    """
    text = text[:_MAX_CHARS]

    try:
        response = _comprehend_medical.detect_entities_v2(Text=text)
    except Exception as exc:
        logger.exception("Comprehend Medical detect_entities_v2 failed: %s", exc)
        return {"entities": []}

    entities = []
    for ent in response.get("Entities", []):
        if ent.get("Score", 0) < 0.5:
            continue

        traits   = [t["Name"] for t in ent.get("Traits", []) if t.get("Score", 0) >= 0.5]
        attrs    = [
            {
                "text":  a["Text"],
                "type":  a["Type"],
                "score": round(a.get("Score", 0.0), 4),
            }
            for a in ent.get("Attributes", [])
            if a.get("Score", 0) >= 0.5
        ]

        entities.append({
            "text":       ent["Text"],
            "category":   ent["Category"],
            "type":       ent["Type"],
            "traits":     traits,
            "score":      round(ent["Score"], 4),
            "attributes": attrs,
        })

    logger.info("Comprehend Medical extracted %d entities", len(entities))
    return {"entities": entities}
