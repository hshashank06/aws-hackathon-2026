"""
rekognition_utils.py
====================
Wraps Amazon Rekognition for document authenticity validation.

  detect_document_validity(s3_bucket, s3_key)
      → { "valid": bool, "confidence": float, "labels": list, "detected_text": list }

Validation logic
----------------
- DetectLabels  : expects "Document", "Paper", "Text", "Page", "Invoice", etc.
  Non-document labels (e.g. only "Person", "Dog") → invalid.
- DetectText    : expects at least one detected word (empty page → invalid).
- Overall confidence = average of matched document-class label scores.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)

AWS_REGION: str = os.environ.get("AWS_REGION", "us-east-1")

_rekognition = boto3.client("rekognition", region_name=AWS_REGION)

# Labels we consider "document-like" — presence of ≥1 raises validity
_DOCUMENT_LABELS = {
    "Document", "Text", "Paper", "Page", "Invoice",
    "Receipt", "Form", "Letter", "Report", "File"
}
_CONFIDENCE_THRESHOLD = 0.50   # minimum average label confidence to accept
_MIN_DETECTED_WORDS   = 3      # minimum words Rekognition must find


def detect_document_validity(
    s3_bucket: str,
    s3_key: str,
) -> dict[str, Any]:
    """
    Validate that an S3 object looks like a genuine document.

    Returns
    -------
    {
      "valid":          bool,
      "confidence":     float,   # 0.0–1.0
      "reason":         str,
      "labels":         list[str],   # matched document-class labels
      "detected_text":  list[str],   # first 10 detected text blocks
    }
    """
    s3_ref = {"S3Object": {"Bucket": s3_bucket, "Name": s3_key}}

    # ------------------------------------------------------------------ Labels
    try:
        label_response = _rekognition.detect_labels(
            Image=s3_ref,
            MaxLabels=20,
            MinConfidence=50.0,
        )
    except Exception as exc:
        logger.exception("Rekognition detect_labels failed for %s/%s", s3_bucket, s3_key)
        return {
            "valid": False,
            "confidence": 0.0,
            "reason": f"Rekognition label detection error: {exc}",
            "labels": [],
            "detected_text": [],
        }

    all_labels = {lbl["Name"]: lbl["Confidence"] / 100.0 for lbl in label_response.get("Labels", [])}
    matched = {name: conf for name, conf in all_labels.items() if name in _DOCUMENT_LABELS}

    # ------------------------------------------------------------------ Text
    try:
        text_response = _rekognition.detect_text(Image=s3_ref)
    except Exception as exc:
        logger.exception("Rekognition detect_text failed for %s/%s", s3_bucket, s3_key)
        return {
            "valid": False,
            "confidence": 0.0,
            "reason": f"Rekognition text detection error: {exc}",
            "labels": list(matched.keys()),
            "detected_text": [],
        }

    # Only WORD detections (not LINE) for the word count
    words = [
        d["DetectedText"]
        for d in text_response.get("TextDetections", [])
        if d["Type"] == "WORD"
    ]

    # ------------------------------------------------------------------ Decision
    if not matched:
        return {
            "valid": False,
            "confidence": 0.0,
            "reason": "No document-class labels detected by Rekognition.",
            "labels": list(all_labels.keys()),
            "detected_text": words[:10],
        }

    avg_confidence = sum(matched.values()) / len(matched)

    if len(words) < _MIN_DETECTED_WORDS:
        return {
            "valid": False,
            "confidence": avg_confidence,
            "reason": f"Too few words detected ({len(words)} < {_MIN_DETECTED_WORDS}).",
            "labels": list(matched.keys()),
            "detected_text": words,
        }

    if avg_confidence < _CONFIDENCE_THRESHOLD:
        return {
            "valid": False,
            "confidence": avg_confidence,
            "reason": f"Document confidence {avg_confidence:.2f} below threshold {_CONFIDENCE_THRESHOLD}.",
            "labels": list(matched.keys()),
            "detected_text": words[:10],
        }

    logger.info(
        "Document %s/%s valid — labels: %s, words: %d, confidence: %.2f",
        s3_bucket, s3_key, list(matched.keys()), len(words), avg_confidence,
    )
    return {
        "valid": True,
        "confidence": round(avg_confidence, 4),
        "reason": "Document passed validation.",
        "labels": list(matched.keys()),
        "detected_text": words[:10],
    }
