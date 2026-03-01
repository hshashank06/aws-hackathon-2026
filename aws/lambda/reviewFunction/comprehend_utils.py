"""
comprehend_utils.py
===================
Wraps Amazon Comprehend (standard NLP) to extract key phrases and entities
from bill and insurance claim text.

Used for:
  - hospitalBill    → bill_extractor identifies billNo, amounts
  - insuranceClaim  → claim_extractor identifies claimId, amounts

Public API
----------
  analyze_text(text)
      → {
            "key_phrases": list[str],
            "entities":    list[{ "text": str, "type": str, "score": float }]
         }
"""

from __future__ import annotations

import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)

AWS_REGION: str = os.environ.get("AWS_REGION", "us-east-1")

_comprehend = boto3.client("comprehend", region_name=AWS_REGION)

# Comprehend has a 5000-byte limit per request
_MAX_BYTES = 4_900


def analyze_text(text: str) -> dict[str, Any]:
    """
    Run Comprehend DetectKeyPhrases + DetectEntities on the supplied text.

    Text is truncated to _MAX_BYTES if needed (Comprehend API limit).

    Returns
    -------
    {
      "key_phrases": list[str],
      "entities":    list[{ "text": str, "type": str, "score": float }]
    }
    """
    text = _truncate(text)

    key_phrases: list[str] = []
    entities: list[dict] = []

    try:
        kp_response = _comprehend.detect_key_phrases(Text=text, LanguageCode="en")
        key_phrases = [
            kp["Text"]
            for kp in kp_response.get("KeyPhrases", [])
            if kp.get("Score", 0) >= 0.5
        ]
    except Exception as exc:
        logger.exception("Comprehend detect_key_phrases failed: %s", exc)

    try:
        ent_response = _comprehend.detect_entities(Text=text, LanguageCode="en")
        entities = [
            {
                "text":  ent["Text"],
                "type":  ent["Type"],
                "score": round(ent.get("Score", 0.0), 4),
            }
            for ent in ent_response.get("Entities", [])
            if ent.get("Score", 0) >= 0.5
        ]
    except Exception as exc:
        logger.exception("Comprehend detect_entities failed: %s", exc)

    logger.info(
        "Comprehend extracted %d key phrases, %d entities",
        len(key_phrases), len(entities),
    )
    return {
        "key_phrases": key_phrases,
        "entities":    entities,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _truncate(text: str) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= _MAX_BYTES:
        return text
    return encoded[:_MAX_BYTES].decode("utf-8", errors="ignore")
