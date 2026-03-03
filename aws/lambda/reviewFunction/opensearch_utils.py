"""
opensearch_utils.py
-------------------
Utilities for indexing review documents into Amazon OpenSearch Service.

Uses SigV4 signing via botocore so no extra third-party packages are needed
(the botocore package is already present in the Lambda runtime).

Environment variables
---------------------
OPENSEARCH_ENDPOINT      – Required. Full HTTPS URL of the OpenSearch domain.
                           e.g. https://search-myapp-xxx.us-east-1.es.amazonaws.com
OPENSEARCH_INDEX         – Index name (default: "reviews")
OPENSEARCH_SERVICE_NAME  – "es" for managed OpenSearch, "aoss" for Serverless (default: "es")
AWS_REGION               – Injected automatically by the Lambda runtime.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from decimal import Decimal
from typing import Any

import boto3
import botocore.auth
import botocore.awsrequest
import botocore.credentials

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OPENSEARCH_ENDPOINT:     str = os.environ.get("OPENSEARCH_ENDPOINT", "").rstrip("/")
OPENSEARCH_INDEX:        str = os.environ.get("OPENSEARCH_INDEX", "reviews")
OPENSEARCH_SERVICE_NAME: str = os.environ.get("OPENSEARCH_SERVICE_NAME", "es")
AWS_REGION:              str = os.environ.get("AWS_REGION", "us-east-1")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decimal_default(obj: Any) -> Any:
    """JSON serialiser that converts Decimal → float / int."""
    if isinstance(obj, Decimal):
        # Preserve integer values where possible
        return int(obj) if obj == int(obj) else float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")


def _sanitise(item: dict[str, Any]) -> dict[str, Any]:
    """Strip Decimal types from a DynamoDB item via a json round-trip."""
    return json.loads(json.dumps(item, default=_decimal_default))


def _build_combined_text(
    review:   dict[str, Any],
    doctor:   dict[str, Any],
    hospital: dict[str, Any],
) -> str:
    """
    Flatten all meaningful text fields from the three records into a single
    string that will be embedded by Titan Embed v2.
    """
    parts: list[str] = []

    # --- Review fields -------------------------------------------------------
    for field in (
        "purposeOfVisit",
        "symptomsAndConditions",
        "surgeryType",
        "diagnosis",
        "medications",
    ):
        val = review.get(field, "")
        if val and isinstance(val, str):
            parts.append(val.strip())

    # Nested review sub-objects
    hospital_review = review.get("hospitalReview", {}) or {}
    for sub_field in ("rating", "reviewTitle", "reviewDetails"):
        val = hospital_review.get(sub_field, "")
        if val and isinstance(val, str):
            parts.append(val.strip())

    doctor_review = review.get("doctorReview", {}) or {}
    for sub_field in ("rating", "reviewTitle", "reviewDetails"):
        val = doctor_review.get(sub_field, "")
        if val and isinstance(val, str):
            parts.append(val.strip())

    # --- Doctor fields -------------------------------------------------------
    for field in ("name", "specialisation", "about", "qualifications"):
        val = doctor.get(field, "")
        if val and isinstance(val, str):
            parts.append(val.strip())

    # --- Hospital fields -----------------------------------------------------
    for field in ("name", "about"):
        val = hospital.get(field, "")
        if val and isinstance(val, str):
            parts.append(val.strip())

    location = hospital.get("location", {}) or {}
    for sub_field in ("city", "state", "country"):
        val = location.get(sub_field, "")
        if val:
            parts.append(str(val).strip())

    services = hospital.get("services", []) or []
    if services:
        parts.append(", ".join(str(s) for s in services if s))

    return " | ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# SigV4 signing
# ---------------------------------------------------------------------------

def _signed_request(method: str, url: str, body_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Make a SigV4-signed HTTP request to OpenSearch without any extra packages.

    Returns the parsed JSON response body as a dict.
    Raises RuntimeError on HTTP ≥ 400.
    """
    body_bytes = json.dumps(body_dict, default=_decimal_default).encode("utf-8")

    # Build an AWSRequest for signing
    aws_request = botocore.awsrequest.AWSRequest(
        method  = method,
        url     = url,
        data    = body_bytes,
        headers = {"Content-Type": "application/json"},
    )

    # Retrieve credentials from the execution role
    session     = botocore.session.get_session()
    credentials = botocore.credentials.Credentials(
        access_key = session.get_credentials().access_key,
        secret_key = session.get_credentials().secret_key,
        token      = session.get_credentials().token,
    )

    signer = botocore.auth.SigV4Auth(credentials, OPENSEARCH_SERVICE_NAME, AWS_REGION)
    signer.add_auth(aws_request)

    prepared   = aws_request.prepare()
    req_object = urllib.request.Request(
        url     = prepared.url,
        data    = body_bytes,
        headers = dict(prepared.headers),
        method  = method.upper(),
    )

    try:
        with urllib.request.urlopen(req_object, timeout=10) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OpenSearch {method} {url} returned HTTP {exc.code}: {body}"
        ) from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def index_review(
    review_id:     str,
    review_item:   dict[str, Any],
    doctor_item:   dict[str, Any],
    hospital_item: dict[str, Any],
    embedding:     list[float],
) -> dict[str, Any]:
    """
    Build and PUT a combined review document into OpenSearch.

    The document stored under ``/<index>/_doc/<reviewId>`` contains:
    - All fields from the DynamoDB Review item (Decimal-sanitised)
    - A ``_doctor``  sub-object with selected doctor fields
    - A ``_hospital`` sub-object with selected hospital fields
    - A ``combinedText`` string used for full-text search
    - A ``contentVector`` 1024-dim dense vector for k-NN / semantic search

    Returns the OpenSearch _doc response dict (e.g. {"result": "created"}).
    """
    if not OPENSEARCH_ENDPOINT:
        logger.warning("OPENSEARCH_ENDPOINT not set — skipping index_review")
        return {"result": "skipped", "reason": "OPENSEARCH_ENDPOINT not configured"}

    # Build a clean document
    doc: dict[str, Any] = _sanitise(review_item)

    doc["_doctor"] = {
        k: doctor_item.get(k)
        for k in ("doctorId", "name", "specialisation", "about", "qualifications", "imageUrl")
        if doctor_item.get(k) is not None
    }

    doc["_hospital"] = {
        k: hospital_item.get(k)
        for k in ("hospitalId", "name", "about", "location", "services", "imageUrl")
        if hospital_item.get(k) is not None
    }

    combined_text      = _build_combined_text(review_item, doctor_item, hospital_item)
    doc["combinedText"] = combined_text

    if embedding:
        doc["contentVector"] = embedding
    else:
        logger.warning("Empty embedding for reviewId=%s — contentVector omitted", review_id)

    # PUT /<index>/_doc/<reviewId>  (idempotent upsert)
    url = f"{OPENSEARCH_ENDPOINT}/{OPENSEARCH_INDEX}/_doc/{review_id}"
    logger.info("Indexing reviewId=%s into %s", review_id, url)

    try:
        result = _signed_request("PUT", url, doc)
        logger.info("OpenSearch index result for %s: %s", review_id, result.get("result"))
        return result
    except RuntimeError as exc:
        logger.exception("OpenSearch indexing failed for %s: %s", review_id, exc)
        # Re-raise so the Lambda reports failure (async invocations retry automatically)
        raise
