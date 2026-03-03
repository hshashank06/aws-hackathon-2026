"""
document_utils.py
=================
S3 pre-signed URL generation and document key helpers for the review workflow.

S3 prefix map:
  hospitalBill    → documents/hospitalBills/<key>
  insuranceClaim  → documents/insuranceClaims/<key>
  medicalRecord   → documents/medicalRecords/<key>

Key format:
  <prefix>/<customerId>_<sha256(filename+epoch)[:12]>.<ext>
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import PurePosixPath


import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

S3_BUCKET: str = os.environ.get("S3_BUCKET", "choco-warriors-db-synthetic-data-us")
AWS_REGION: str = os.environ.get("AWS_REGION", "us-east-1")
PRESIGN_EXPIRY: int = 300  # seconds (5 minutes)

PREFIX_MAP: dict[str, str] = {
    "hospitalBill":   "documents/hospitalBills",
    "insuranceClaim": "documents/insuranceClaims",
    "medicalRecord":  "documents/medicalRecords",
}

# Force SigV4 + virtual-hosted style for pre-signed URL generation.
# - signature_version="s3v4": prevents boto3 from generating legacy SigV2 URLs
#   (AWSAccessKeyId/Signature params) which us-east-1 rejects.
# - addressing_style="virtual": ensures the bucket is in the hostname
#   (bucket.s3.amazonaws.com/key) so the host in the signing key matches
#   the host in the actual HTTP request. Without this, boto3 can use the
#   path-style global endpoint (s3.amazonaws.com/bucket/key) for signing
#   while S3 routes via virtual-hosted, causing a host mismatch.
_s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "virtual"},
    ),
)


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------

def generate_s3_key(customer_id: str, filename: str, document_type: str) -> str:
    """
    Build a deterministic-but-unique S3 key for an uploaded document.

    Parameters
    ----------
    customer_id   : DynamoDB customer PK (e.g. "customer_id_06kzw")
    filename      : original filename supplied by the browser
    document_type : one of the PREFIX_MAP keys

    Returns
    -------
    Full S3 key string, e.g.
    "documents/hospitalBills/customer_id_06kzw_f3a9d812c441.png"
    """
    prefix = PREFIX_MAP.get(document_type)
    if prefix is None:
        raise ValueError(
            f"Unknown documentType '{document_type}'. "
            f"Expected one of: {', '.join(PREFIX_MAP)}"
        )

    # Hash filename + current epoch to guarantee uniqueness across re-uploads
    raw = f"{filename}{time.time()}"
    hash_suffix = hashlib.sha256(raw.encode()).hexdigest()[:12]

    ext = PurePosixPath(filename).suffix.lower()   # e.g. ".png", ".pdf"
    if not ext:
        ext = ".bin"

    key = f"{prefix}/{customer_id}_{hash_suffix}{ext}"
    return key


# ---------------------------------------------------------------------------
# Pre-signed URL
# ---------------------------------------------------------------------------

def generate_presigned_put_url(s3_key: str) -> str:
    """
    Generate a pre-signed PUT URL for browser-to-S3 direct upload.

    ContentType is intentionally excluded from the signed parameters so that
    the browser can PUT without needing to match a specific Content-Type header
    value. The correct file extension is already encoded in s3_key via
    generate_s3_key() which reads it from the original filename.

    Parameters
    ----------
    s3_key : the destination S3 object key (includes correct file extension)

    Returns
    -------
    Pre-signed URL string (valid for PRESIGN_EXPIRY seconds)
    """
    params: dict = {
        "Bucket": S3_BUCKET,
        "Key":    s3_key,
    }

    url = _s3_client.generate_presigned_url(
        "put_object",
        Params=params,
        ExpiresIn=PRESIGN_EXPIRY,
    )
    return url


def get_s3_url(s3_key: str) -> str:
    """Return the public-style HTTPS URL for an S3 object (not pre-signed)."""
    return f"https://{S3_BUCKET}.s3.amazonaws.com/{s3_key}"


def object_exists(s3_key: str) -> bool:
    """Return True if the S3 object exists (used to validate before processing)."""
    try:
        _s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise
