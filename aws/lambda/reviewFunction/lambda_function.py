"""
AWS Lambda – Review CRUD + Document Processing
==============================================
Routes:

  POST   /reviews/presign           → generate_presigned_url_handler
  POST   /reviews/process-document  → process_document_handler
  POST   /reviews                   → create_review
  GET    /reviews                   → list_reviews
  GET    /reviews/{reviewId}        → get_review
  PUT    /reviews/{reviewId}        → update_review
  DELETE /reviews/{reviewId}        → delete_review

Environment variables (required):
  TABLE_NAME         – DynamoDB table name          (default: "Review")
  S3_BUCKET          – S3 bucket for documents      (default: "choco-warriors-db-synthetic-data")
  STEP_FUNCTION_ARN  – ARN of the Synchronous Express Workflow
  BEDROCK_MODEL_ID   – Bedrock model ID             (default: anthropic.claude-3-sonnet-20240229-v1:0)
  AWS_REGION         – injected automatically by Lambda runtime

Review schema (DynamoDB)
------------------------
  reviewId        (PK, String)
  hospitalId      (String)
  doctorId        (String)
  customerId      (String)
  policyId        (String | null)
  purposeOfVisit  (String)
  doctorReview    (Map: { doctorId, doctorReview })
  claim           (Map | null: { claimId, claimAmountApproved, remainingAmountToBePaid })
  payment         (Map: { billNo, amountToBePayed, totalBillAmount, description })
  hospitalReview  (String)
  documentIds     (List[String])
  extractedData   (Map: { hospitalName, doctorName, surgeryType, procedureDate,
                          diagnosis, medications[], confidence })
  verified        (Number: 1 = verified)
  createdAt       (String, "YYYY-MM-DD HH:MM:SS")
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME:        str = os.environ.get("TABLE_NAME",        "Review")
S3_BUCKET:         str = os.environ.get("S3_BUCKET",         "choco-warriors-db-synthetic-data")
STEP_FUNCTION_ARN: str = os.environ.get("STEP_FUNCTION_ARN", "")
PARTITION_KEY:     str = "reviewId"

_dynamodb       = boto3.resource("dynamodb")
table           = _dynamodb.Table(TABLE_NAME)
_states_client  = boto3.client("stepfunctions")

# Local imports (other files in this Lambda package)
import document_utils
import bedrock_utils
import rekognition_utils
import textract_utils
import comprehend_utils
import comprehend_medical_utils
from extractors import bill_extractor, claim_extractor, medical_extractor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)


def _response(status_code: int, body: Any) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }


def _ok(body: Any, status_code: int = 200) -> dict:
    return _response(status_code, body)


def _error(status_code: int, message: str) -> dict:
    return _response(status_code, {"error": message})


def _parse_body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def _get_review_id(event: dict) -> str | None:
    return (event.get("pathParameters") or {}).get("reviewId")


def _get_path(event: dict) -> str:
    """Return the request path (normalised, lower-case)."""
    # REST API
    path = event.get("path", "")
    if not path:
        # HTTP API v2
        path = event.get("requestContext", {}).get("http", {}).get("path", "")
    return path.rstrip("/").lower()


def _get_method(event: dict) -> str:
    return (
        event.get("httpMethod")
        or event.get("requestContext", {}).get("http", {}).get("method", "")
    ).upper()


# ---------------------------------------------------------------------------
# 1. Pre-signed URL handler
# ---------------------------------------------------------------------------

def generate_presigned_url_handler(event: dict) -> dict:
    """
    POST /reviews/presign
    Body: { customerId, filename, documentType }
    Returns: { uploadUrl, s3Key, documentId }
    """
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _error(400, "Invalid JSON in request body.")

    customer_id   = body.get("customerId", "").strip()
    filename      = body.get("filename",   "").strip()
    document_type = body.get("documentType", "").strip()

    missing = [f for f, v in [("customerId", customer_id), ("filename", filename), ("documentType", document_type)] if not v]
    if missing:
        return _error(400, f"Missing required fields: {', '.join(missing)}")

    try:
        s3_key = document_utils.generate_s3_key(customer_id, filename, document_type)
    except ValueError as exc:
        return _error(400, str(exc))

    try:
        upload_url = document_utils.generate_presigned_put_url(s3_key)
    except Exception as exc:
        logger.exception("Failed to generate pre-signed URL")
        return _error(500, f"Could not generate upload URL: {exc}")

    logger.info("Pre-signed URL generated: %s", s3_key)
    return _ok({
        "uploadUrl":  upload_url,
        "s3Key":      s3_key,
        "documentId": s3_key,   # documentId == s3Key (stored in DynamoDB as-is)
        "expiresIn":  document_utils.PRESIGN_EXPIRY,
    })


# ---------------------------------------------------------------------------
# 2. Process document handler  (calls Step Functions Sync Express Workflow)
# ---------------------------------------------------------------------------

def process_document_handler(event: dict) -> dict:
    """
    POST /reviews/process-document
    Body: { documentId, s3Key, documentType }
    Returns extracted fields + { valid, confidence, s3Url }
    """
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _error(400, "Invalid JSON in request body.")

    document_id   = body.get("documentId",   "").strip()
    s3_key        = body.get("s3Key",        "").strip()
    document_type = body.get("documentType", "").strip()

    missing = [f for f, v in [("documentId", document_id), ("s3Key", s3_key), ("documentType", document_type)] if not v]
    if missing:
        return _error(400, f"Missing required fields: {', '.join(missing)}")

    if not STEP_FUNCTION_ARN:
        return _error(500, "STEP_FUNCTION_ARN environment variable is not set.")

    # Verify the object exists in S3 before handing it to Step Functions
    if not document_utils.object_exists(s3_key):
        return _error(404, f"Document '{s3_key}' not found in S3. Upload it first via /reviews/presign.")

    sf_input = json.dumps({
        "s3Bucket":     S3_BUCKET,
        "s3Key":        s3_key,
        "documentType": document_type,
        "documentId":   document_id,
    })

    try:
        sf_response = _states_client.start_sync_execution(
            stateMachineArn=STEP_FUNCTION_ARN,
            name=f"doc-{uuid.uuid4().hex[:12]}",
            input=sf_input,
        )
    except Exception as exc:
        logger.exception("Step Functions execution failed")
        return _error(500, f"Document processing failed: {exc}")

    if sf_response.get("status") == "FAILED":
        cause = sf_response.get("cause", "Unknown failure")
        logger.error("Step Functions execution FAILED: %s", cause)
        return _error(422, f"Document processing failed: {cause}")

    try:
        output = json.loads(sf_response.get("output", "{}"))
    except (json.JSONDecodeError, TypeError):
        output = {}

    output["documentId"] = document_id
    output["s3Url"]      = document_utils.get_s3_url(s3_key)

    return _ok(output)


# ---------------------------------------------------------------------------
# 3. Create review
# ---------------------------------------------------------------------------

def create_review(event: dict) -> dict:
    """
    POST /reviews
    Assembles a full review record, generates payment.description via Bedrock,
    then writes to DynamoDB.
    """
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _error(400, "Invalid JSON in request body.")

    required = ["hospitalId", "doctorId", "customerId", "purposeOfVisit",
                "doctorReview", "hospitalReview", "payment", "documentIds"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return _error(400, f"Missing required fields: {', '.join(missing)}")

    review_id  = f"review_{uuid.uuid4().hex[:10]}"
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    payment      = body.get("payment", {})
    extracted    = body.get("extractedData", {})
    claim        = body.get("claim")      # may be None / null

    # Generate payment description via Bedrock
    try:
        payment["description"] = bedrock_utils.generate_payment_description(
            payment=payment,
            extracted_data=extracted,
            claim=claim,
        )
    except Exception as exc:
        logger.warning("Bedrock payment description generation failed: %s", exc)
        payment["description"] = ""

    item: dict[str, Any] = {
        PARTITION_KEY:   review_id,
        "hospitalId":    body["hospitalId"],
        "doctorId":      body["doctorId"],
        "customerId":    body["customerId"],
        "policyId":      body.get("policyId"),        # nullable
        "purposeOfVisit":body["purposeOfVisit"],
        "doctorReview":  body["doctorReview"],
        "hospitalReview":body["hospitalReview"],
        "payment":       payment,
        "claim":         claim,                        # nullable
        "documentIds":   body.get("documentIds", []),
        "extractedData": extracted,
        "verified":      1,
        "createdAt":     created_at,
    }

    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(#pk)",
            ExpressionAttributeNames={"#pk": PARTITION_KEY},
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "ConditionalCheckFailedException":
            return _error(409, f"Review '{review_id}' already exists — collision, retry.")
        logger.exception("DynamoDB put_item failed")
        return _error(500, "Failed to create review.")

    logger.info("Created review %s", review_id)
    return _ok(item, status_code=201)


# ---------------------------------------------------------------------------
# 4. Get review
# ---------------------------------------------------------------------------

def get_review(event: dict) -> dict:
    review_id = _get_review_id(event)
    if not review_id:
        return _error(400, "Missing path parameter: reviewId")

    try:
        result = table.get_item(Key={PARTITION_KEY: review_id})
    except ClientError:
        logger.exception("DynamoDB get_item failed")
        return _error(500, "Failed to retrieve review.")

    item = result.get("Item")
    if not item:
        return _error(404, f"Review '{review_id}' not found.")
    return _ok(item)


# ---------------------------------------------------------------------------
# 5. List reviews
# ---------------------------------------------------------------------------

def list_reviews(event: dict) -> dict:
    query_params = event.get("queryStringParameters") or {}
    try:
        limit = min(int(query_params.get("limit", 20)), 100)
    except ValueError:
        limit = 20

    scan_kwargs: dict[str, Any] = {"Limit": limit}
    last_key_raw = query_params.get("lastKey")
    if last_key_raw:
        try:
            scan_kwargs["ExclusiveStartKey"] = json.loads(last_key_raw)
        except (json.JSONDecodeError, TypeError):
            return _error(400, "Invalid lastKey token.")

    # Optional filter by customerId
    customer_id = query_params.get("customerId")
    if customer_id:
        scan_kwargs["FilterExpression"] = "customerId = :cid"
        scan_kwargs["ExpressionAttributeValues"] = {":cid": customer_id}

    try:
        result = table.scan(**scan_kwargs)
    except ClientError:
        logger.exception("DynamoDB scan failed")
        return _error(500, "Failed to list reviews.")

    response_body: dict[str, Any] = {
        "items": result.get("Items", []),
        "count": result.get("Count", 0),
    }
    if "LastEvaluatedKey" in result:
        response_body["lastKey"] = json.dumps(result["LastEvaluatedKey"])

    return _ok(response_body)


# ---------------------------------------------------------------------------
# 6. Update review
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Step Functions action handlers
# (called by the document-processing state machine, not directly by API GW)
# ---------------------------------------------------------------------------

def _action_rekognition_validate(event: dict) -> dict:
    """action: rekognition_validate — validate an S3 object as a genuine document."""
    result = rekognition_utils.detect_document_validity(
        s3_bucket=event["s3Bucket"],
        s3_key=event["s3Key"],
    )
    return result  # { valid, confidence, reason, labels, detected_text }


def _action_textract_extract(event: dict) -> dict:
    """action: textract_extract — extract raw text, key-values and tables."""
    result = textract_utils.extract_document(
        s3_bucket=event["s3Bucket"],
        s3_key=event["s3Key"],
    )
    return result  # { raw_text, key_values, tables }


def _action_extract_bill(event: dict) -> dict:
    """action: extract_bill — Comprehend → bill payment fields."""
    textract_result = {
        "raw_text":   event.get("raw_text", ""),
        "key_values": event.get("key_values", {}),
        "tables":     event.get("tables", []),
    }
    comprehend_result = comprehend_utils.analyze_text(textract_result["raw_text"])
    payment = bill_extractor.extract_payment(textract_result, comprehend_result)
    return {
        "valid":      True,
        "confidence": comprehend_result.get("confidence", 0.0),
        "payment":    payment,
    }


def _action_extract_claim(event: dict) -> dict:
    """action: extract_claim — Comprehend → insurance claim fields."""
    textract_result = {
        "raw_text":   event.get("raw_text", ""),
        "key_values": event.get("key_values", {}),
        "tables":     event.get("tables", []),
    }
    comprehend_result = comprehend_utils.analyze_text(textract_result["raw_text"])
    claim = claim_extractor.extract_claim(textract_result, comprehend_result)
    return {
        "valid":      True,
        "confidence": comprehend_result.get("confidence", 0.0),
        "claim":      claim,
    }


def _action_extract_medical(event: dict) -> dict:
    """action: extract_medical — Comprehend Medical → extractedData fields."""
    textract_result = {
        "raw_text":   event.get("raw_text", ""),
        "key_values": event.get("key_values", {}),
        "tables":     event.get("tables", []),
    }
    cm_result  = comprehend_medical_utils.analyze_medical_text(textract_result["raw_text"])
    extracted  = medical_extractor.extract_medical_data(textract_result, cm_result)
    confidence = extracted.get("confidence", 0.0)
    return {
        "valid":         True,
        "confidence":    confidence,
        "extractedData": extracted,
    }


_ACTION_HANDLERS = {
    "rekognition_validate": _action_rekognition_validate,
    "textract_extract":     _action_textract_extract,
    "extract_bill":         _action_extract_bill,
    "extract_claim":        _action_extract_claim,
    "extract_medical":      _action_extract_medical,
}


UPDATABLE_REVIEW_FIELDS = {
    "purposeOfVisit", "doctorReview", "hospitalReview",
    "payment", "claim", "extractedData", "documentIds",
    "hospitalId", "doctorId", "policyId", "verified",
}


def update_review(event: dict) -> dict:
    review_id = _get_review_id(event)
    if not review_id:
        return _error(400, "Missing path parameter: reviewId")

    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _error(400, "Invalid JSON in request body.")

    if not body:
        return _error(400, "Request body must not be empty.")

    updates = {k: v for k, v in body.items() if k in UPDATABLE_REVIEW_FIELDS}
    if not updates:
        return _error(400, f"No updatable fields provided. Allowed: {sorted(UPDATABLE_REVIEW_FIELDS)}")

    set_expressions = []
    expr_attr_names: dict[str, str] = {}
    expr_attr_values: dict[str, Any] = {}

    for field, value in updates.items():
        ph = f"#f_{field}"
        vk = f":v_{field}"
        set_expressions.append(f"{ph} = {vk}")
        expr_attr_names[ph] = field
        expr_attr_values[vk] = value

    try:
        result = table.update_item(
            Key={PARTITION_KEY: review_id},
            UpdateExpression="SET " + ", ".join(set_expressions),
            ExpressionAttributeNames={**expr_attr_names, "#pk": PARTITION_KEY},
            ExpressionAttributeValues=expr_attr_values,
            ConditionExpression="attribute_exists(#pk)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return _error(404, f"Review '{review_id}' not found.")
        logger.exception("DynamoDB update_item failed")
        return _error(500, "Failed to update review.")

    return _ok(result["Attributes"])


# ---------------------------------------------------------------------------
# 7. Delete review
# ---------------------------------------------------------------------------

def delete_review(event: dict) -> dict:
    review_id = _get_review_id(event)
    if not review_id:
        return _error(400, "Missing path parameter: reviewId")

    try:
        result = table.delete_item(
            Key={PARTITION_KEY: review_id},
            ConditionExpression="attribute_exists(#pk)",
            ExpressionAttributeNames={"#pk": PARTITION_KEY},
            ReturnValues="ALL_OLD",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return _error(404, f"Review '{review_id}' not found.")
        logger.exception("DynamoDB delete_item failed")
        return _error(500, "Failed to delete review.")

    return _ok({"message": f"Review '{review_id}' deleted.", "deleted": result.get("Attributes", {})})


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def lambda_handler(event: dict, context: Any) -> dict:
    """Main Lambda entry point wired to API Gateway proxy integration."""

    # ── Step Functions action dispatch ──────────────────────────────────────
    # When invoked directly by the state machine the event has an "action" key
    # and is NOT an API Gateway proxy event.
    action = event.get("action")
    if action:
        handler_fn = _ACTION_HANDLERS.get(action)
        if handler_fn is None:
            return {"error": f"Unknown action '{action}'"}
        try:
            return handler_fn(event)
        except Exception as exc:
            logger.exception("Action '%s' raised an unexpected error", action)
            raise  # Let Step Functions handle the failure

    # ── API Gateway proxy dispatch ───────────────────────────────────────────
    method    = _get_method(event)
    path      = _get_path(event)
    review_id = _get_review_id(event)

    logger.info("Routing %s %s (reviewId=%s)", method, path, review_id)

    # Sub-resource routes (must be checked before the generic /reviews routes)
    if method == "POST" and path.endswith("/reviews/presign"):
        return generate_presigned_url_handler(event)

    if method == "POST" and path.endswith("/reviews/process-document"):
        return process_document_handler(event)

    # Standard CRUD routes
    if method == "POST"   and not review_id:
        return create_review(event)
    if method == "GET"    and not review_id:
        return list_reviews(event)
    if method == "GET"    and review_id:
        return get_review(event)
    if method == "PUT"    and review_id:
        return update_review(event)
    if method == "DELETE" and review_id:
        return delete_review(event)

    return _error(405, f"Method '{method}' on path '{path}' is not supported.")
