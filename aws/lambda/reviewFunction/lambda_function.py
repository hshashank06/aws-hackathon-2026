"""
AWS Lambda – Review CRUD + Document Processing
==============================================
Routes:

  GET    /reviews/documents          → get_user_documents_handler
  GET    /reviews/documents/download → get_document_download_url_handler
  POST   /reviews/presign           → generate_presigned_url_handler
  POST   /reviews/process-document  → process_document_handler
  DELETE /reviews/documents         → delete_document_handler
  POST   /reviews                   → create_review
  GET    /reviews                   → list_reviews
  GET    /reviews/{reviewId}        → get_review
  PUT    /reviews/{reviewId}        → update_review
  DELETE /reviews/{reviewId}        → delete_review

Environment variables (required):
  TABLE_NAME                 – DynamoDB Review table name     (default: "Review")
  DOCTOR_TABLE_NAME          – DynamoDB Doctor table name     (default: "Doctor")
  HOSPITAL_TABLE_NAME        – DynamoDB Hospital table name   (default: "Hospital")
  DYNAMODB_REGION            – Region where DynamoDB tables live (default: "eu-north-1")
  S3_BUCKET                  – S3 bucket for documents        (default: "choco-warriors-db-synthetic-data-us")
  STEP_FUNCTION_ARN          – ARN of the Sync Express Workflow
  BEDROCK_MODEL_ID           – Bedrock chat model ID          (default: anthropic.claude-3-sonnet-20240229-v1:0)
  BEDROCK_EMBEDDING_MODEL_ID – Bedrock embedding model        (default: amazon.titan-embed-text-v2:0)
  OPENSEARCH_ENDPOINT        – OpenSearch domain endpoint URL (e.g. https://search-xxx.es.amazonaws.com)
  OPENSEARCH_INDEX           – OpenSearch index name          (default: "reviews")
  FUNCTION_NAME              – This Lambda's own function name (for async self-invocation)
  AWS_REGION                 – injected automatically by Lambda runtime

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

TABLE_NAME:          str = os.environ.get("TABLE_NAME",          "Review")
DOCTOR_TABLE_NAME:   str = os.environ.get("DOCTOR_TABLE_NAME",   "Doctor")
HOSPITAL_TABLE_NAME: str = os.environ.get("HOSPITAL_TABLE_NAME", "Hospital")
S3_BUCKET:           str = os.environ.get("S3_BUCKET",           "choco-warriors-db-synthetic-data-us")
STEP_FUNCTION_ARN:   str = os.environ.get("STEP_FUNCTION_ARN",   "arn:aws:states:us-east-1:582027981081:stateMachine:DocumentProcessingWorkflowUS")
FUNCTION_NAME:       str = os.environ.get("FUNCTION_NAME",       "reviewFunction")
AWS_REGION:          str = os.environ.get("AWS_REGION",          "us-east-1")
DYNAMODB_REGION:     str = os.environ.get("DYNAMODB_REGION",     "eu-north-1")
PARTITION_KEY:       str = "reviewId"

_dynamodb        = boto3.resource("dynamodb", region_name=DYNAMODB_REGION)
table            = _dynamodb.Table(TABLE_NAME)
_doctor_table    = _dynamodb.Table(DOCTOR_TABLE_NAME)
_hospital_table  = _dynamodb.Table(HOSPITAL_TABLE_NAME)
_states_client   = boto3.client("stepfunctions", region_name=AWS_REGION)
_lambda_client   = boto3.client("lambda",        region_name=AWS_REGION)

# Local imports (other files in this Lambda package)
import document_utils
import bedrock_utils
import opensearch_utils
import textract_utils
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
        "body": json.dumps(body, cls=DecimalEncoder, ensure_ascii=False),
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


def _sanitize_for_dynamo(obj: Any) -> Any:
    """
    Recursively convert Python floats to Decimal so boto3's DynamoDB resource
    can serialise the value.  DynamoDB's TypeSerializer rejects raw floats
    (raises TypeError: "Float types are not supported. Use Decimal types instead.").
    Also strips top-level None values from dicts since DynamoDB will reject
    a NULL attribute write when strict mode is on.
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _sanitize_for_dynamo(v) for k, v in obj.items() if v is not None or True}
    if isinstance(obj, list):
        return [_sanitize_for_dynamo(v) for v in obj]
    return obj


def _get_review_id(event: dict) -> str | None:
    return (event.get("pathParameters") or {}).get("reviewId")


def _get_document_id(event: dict) -> str | None:
    return (event.get("pathParameters") or {}).get("documentId")


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
# 0a. User documents handler  (lists all documents for a given customerId)
# ---------------------------------------------------------------------------

# Maps the lowercased S3 prefix to a human-readable document type label.
_PREFIX_TO_DOC_TYPE: dict[str, str] = {
    "documents/hospitalbills":    "Payment Receipt",
    "documents/insuranceclaims":  "Insurance Claim",
    "documents/medicalrecords":   "Discharge Summary",
}

_s3_meta_client = boto3.client("s3", region_name=AWS_REGION)


def _s3_head(s3_key: str) -> dict:
    """Return S3 HEAD object metadata, or {} on any error."""
    try:
        return _s3_meta_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
    except Exception as exc:
        logger.warning("S3 head_object failed for key '%s': %s", s3_key, exc)
        return {}


def _format_size(size_bytes: int) -> str:
    """Format bytes into a human-readable MB / KB string."""
    if size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def _infer_doc_type(s3_key: str) -> str:
    """Derive the human-readable document type from the S3 key prefix."""
    lower = s3_key.lower()
    for prefix, label in _PREFIX_TO_DOC_TYPE.items():
        if lower.startswith(prefix):
            return label
    return "Document"


def get_user_documents_handler(event: dict) -> dict:
    """
    GET /reviews/documents?customerId=<id>

    Returns all documents (from every review) that belong to the given customer.
    Each entry contains:
      id, name, type, date, size, hospital, verified, s3Key

    The customerId is the Cognito sub (stable user ID) stored in Review.customerId.
    """
    query_params = event.get("queryStringParameters") or {}
    customer_id = (query_params.get("customerId") or "").strip()
    if not customer_id:
        return _error(400, "Missing required query parameter: customerId")

    # ── 1. Fetch all reviews for this customer (full scan with filter) ──────
    try:
        scan_kwargs: dict[str, Any] = {
            "FilterExpression": "customerId = :cid",
            "ExpressionAttributeValues": {":cid": customer_id},
        }
        result = table.scan(**scan_kwargs)
        reviews: list[dict] = list(result.get("Items", []))
        while "LastEvaluatedKey" in result:
            result = table.scan(
                **scan_kwargs,
                ExclusiveStartKey=result["LastEvaluatedKey"],
            )
            reviews.extend(result.get("Items", []))
    except ClientError:
        logger.exception("DynamoDB scan failed for customerId=%s", customer_id)
        return _error(500, "Failed to retrieve user documents.")

    logger.info("Found %d review(s) for customerId=%s", len(reviews), customer_id)

    # ── 2. Collect unique documents across all reviews ───────────────────────
    documents: list[dict] = []
    seen_doc_ids: set[str] = set()

    for review in reviews:
        doc_ids: list[str] = review.get("documentIds") or []
        if not doc_ids:
            continue

        extracted  = review.get("extractedData") or {}
        hospital   = extracted.get("hospitalName") or review.get("hospitalId", "")
        surgery    = extracted.get("surgeryType", "")
        verified   = int(review.get("verified", 0)) == 1
        # createdAt is "YYYY-MM-DD HH:MM:SS" – take only the date part
        created_at = (review.get("createdAt") or "")[:10]

        for s3_key in doc_ids:
            if s3_key in seen_doc_ids:
                continue
            seen_doc_ids.add(s3_key)

            doc_type = _infer_doc_type(s3_key)
            # Build a descriptive name: "<Procedure> - <DocType>" or just docType
            name = f"{surgery} - {doc_type}" if surgery else doc_type

            # S3 HEAD for the file size (best-effort)
            meta = _s3_head(s3_key)
            size_bytes = meta.get("ContentLength", 0)
            size_str = _format_size(size_bytes) if size_bytes else "—"

            documents.append({
                "id":       s3_key,
                "name":     name,
                "type":     doc_type,
                "date":     created_at,
                "size":     size_str,
                "hospital": hospital,
                "verified": verified,
                "s3Key":    s3_key,
            })

    # Sort newest first
    documents.sort(key=lambda d: d["date"], reverse=True)

    return _ok({"documents": documents, "count": len(documents)})


# ---------------------------------------------------------------------------
# 0b. Download document handler  (returns a pre-signed S3 GET URL)
# ---------------------------------------------------------------------------

def get_document_download_url_handler(event: dict) -> dict:
    """
    GET /reviews/documents/download?documentId=<s3Key>
    Returns a short-lived pre-signed S3 GET URL so the browser can download the file.
    """
    query_params = event.get("queryStringParameters") or {}
    document_id = (query_params.get("documentId") or "").strip()
    if not document_id:
        return _error(400, "Missing required query parameter: documentId")

    s3_key = document_id  # documentId == s3Key by convention

    try:
        s3_dl_client = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "eu-north-1"))
        download_url = s3_dl_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": s3_key},
            ExpiresIn=300,  # 5 minutes
        )
    except Exception as exc:
        logger.exception("Failed to generate presigned download URL for '%s'", s3_key)
        return _error(500, f"Failed to generate download URL: {exc}")

    filename = s3_key.split("/")[-1]
    return _ok({"downloadUrl": download_url, "filename": filename, "expiresIn": 300})


# ---------------------------------------------------------------------------
# 0c. Delete document handler  (removes a previously-uploaded S3 object)
# ---------------------------------------------------------------------------

def delete_document_handler(event: dict) -> dict:
    """
    DELETE /reviews/documents
    Body: { "documentId": "<s3Key>" }
    Permanently removes an uploaded document from S3.
    Safe to call even if the object no longer exists.
    """
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _error(400, "Invalid JSON in request body.")

    document_id = (body.get("documentId") or "").strip()
    if not document_id:
        return _error(400, "Missing required field: documentId")

    s3_key = document_id  # documentId == s3Key by convention (see generate_presigned_url_handler)

    try:
        s3_client = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "eu-north-1"))
        s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        logger.info("Deleted S3 object: s3://%s/%s", S3_BUCKET, s3_key)
    except Exception as exc:
        logger.exception("Failed to delete S3 object '%s'", s3_key)
        return _error(500, f"Failed to delete document: {exc}")

    return _ok({"message": f"Document '{s3_key}' deleted from S3.", "documentId": document_id})


# ---------------------------------------------------------------------------
# 1. Pre-signed URL handler
# ---------------------------------------------------------------------------

def generate_presigned_url_handler(event: dict) -> dict:
    """
    POST /reviews/presign
    Body: { customerId, filename, documentType }
    Returns: { uploadUrl, s3Key, documentId, expiresIn }
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
# Background indexing  (async self-invocation after review creation)
# ---------------------------------------------------------------------------

def _fire_index_review(review_id: str, doctor_id: str, hospital_id: str) -> None:
    """
    Asynchronously invoke THIS Lambda with action='index_review'.
    InvocationType='Event' → fire-and-forget (202, no wait).
    The caller's POST /reviews response is NOT delayed.
    """
    payload = json.dumps({
        "action":     "index_review",
        "reviewId":   review_id,
        "doctorId":   doctor_id,
        "hospitalId": hospital_id,
    }).encode()

    try:
        _lambda_client.invoke(
            FunctionName   = FUNCTION_NAME,
            InvocationType = "Event",   # async — caller does not wait
            Payload        = payload,
        )
        logger.info("Fired async index_review for reviewId=%s", review_id)
    except Exception as exc:
        # Non-fatal — indexing failure must NEVER block review creation
        logger.warning("Could not fire async index_review: %s", exc)


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
            Item=_sanitize_for_dynamo(item),
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

    # TODO: re-enable once POST /reviews mapping layer is confirmed correct
    # _fire_index_review(
    #     review_id   = review_id,
    #     doctor_id   = body["doctorId"],
    #     hospital_id = body["hospitalId"],
    # )

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
    """
    GET /reviews
    Returns all reviews with optional filtering.
    Query params:
      customerId – filter by customer ID
      hospitalId – filter by hospital ID
      doctorId   – filter by doctor ID
      policyId   – filter by insurance policy ID
    
    Multiple filters can be combined (AND logic).
    """
    query_params = event.get("queryStringParameters") or {}

    scan_kwargs: dict[str, Any] = {}

    # Build filter expressions for multiple optional filters
    filter_expressions = []
    expr_values: dict[str, str] = {}

    customer_id = query_params.get("customerId")
    if customer_id:
        filter_expressions.append("customerId = :cid")
        expr_values[":cid"] = customer_id

    hospital_id = query_params.get("hospitalId")
    if hospital_id:
        filter_expressions.append("hospitalId = :hid")
        expr_values[":hid"] = hospital_id

    doctor_id = query_params.get("doctorId")
    if doctor_id:
        filter_expressions.append("doctorId = :did")
        expr_values[":did"] = doctor_id

    policy_id = query_params.get("policyId")
    if policy_id:
        filter_expressions.append("policyId = :pid")
        expr_values[":pid"] = policy_id

    if filter_expressions:
        scan_kwargs["FilterExpression"] = " AND ".join(filter_expressions)
        scan_kwargs["ExpressionAttributeValues"] = expr_values

    logger.info("list_reviews | filters=%s | values=%s", filter_expressions, expr_values)

    # Use the ReviewIndex GSI (customerId PK) for efficient customer queries.
    # Fall back to full-table paginated scan for other filters or no filter.
    items: list = []
    try:
        if customer_id and not hospital_id and not doctor_id and not policy_id:
            # Fast path: query the GSI — no table scan needed
            query_kwargs: dict[str, Any] = {
                "IndexName": "ReviewIndex",
                "KeyConditionExpression": "customerId = :cid",
                "ExpressionAttributeValues": {":cid": customer_id},
            }
            result = table.query(**query_kwargs)
            items.extend(result.get("Items", []))
            while "LastEvaluatedKey" in result:
                query_kwargs["ExclusiveStartKey"] = result["LastEvaluatedKey"]
                result = table.query(**query_kwargs)
                items.extend(result.get("Items", []))
            logger.info("list_reviews (GSI query) done | Returned=%d", len(items))
        else:
            # Slow path: paginated scan (needed for multi-field filters or no filter)
            result = table.scan(**scan_kwargs)
            items.extend(result.get("Items", []))
            while "LastEvaluatedKey" in result:
                scan_kwargs["ExclusiveStartKey"] = result["LastEvaluatedKey"]
                result = table.scan(**scan_kwargs)
                items.extend(result.get("Items", []))
            logger.info("list_reviews (scan) done | Returned=%d", len(items))
    except ClientError:
        logger.exception("DynamoDB list_reviews failed")
        return _error(500, "Failed to list reviews.")

    logger.info("list_reviews done | Returned=%d", len(items))

    return _ok({"items": items, "count": len(items)})


# ---------------------------------------------------------------------------
# 6. Update review
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Step Functions action handlers
# (called by the document-processing state machine, not directly by API GW)
# ---------------------------------------------------------------------------

def _action_textract_extract(event: dict) -> dict:
    """action: textract_extract — extract raw text, key-values and tables."""
    result = textract_utils.extract_document(
        s3_bucket=event["s3Bucket"],
        s3_key=event["s3Key"],
    )
    return result  # { raw_text, key_values, tables }


_DOC_TYPE_LABELS: dict[str, str] = {
    "insuranceClaim": "an insurance claim document",
    "medicalRecord":  "a medical record / discharge summary",
    "hospitalBill":   "a hospital bill",
}


def _action_extract_bill(event: dict) -> dict:
    """action: extract_bill — Textract → Bedrock Claude → bill payment fields."""
    textract_result = {
        "raw_text":   event.get("raw_text", ""),
        "key_values": event.get("key_values", {}),
        "tables":     event.get("tables", []),
    }

    # Validate that the uploaded document is actually a hospital bill before
    # running the expensive Textract → Bedrock extraction pipeline.
    classification = bedrock_utils.classify_document_type(textract_result["raw_text"])
    doc_type = classification.get("documentType", "unknown")
    if doc_type != "hospitalBill":
        found_label = _DOC_TYPE_LABELS.get(doc_type, "an unrecognized document")
        reason = (
            f"Invalid document: expected a hospital bill but received {found_label}. "
            "Please upload the correct file."
        )
        logger.warning("[extract_bill] Wrong document type detected: %s – %s", doc_type, reason)
        return {
            "valid":   False,
            "reason":  reason,
            "payment": {},
        }

    payment = bill_extractor.extract_payment(textract_result)
    return {
        "valid":   True,
        "reason":  "",
        "payment": payment,
    }


def _action_extract_claim(event: dict) -> dict:
    """action: extract_claim — Textract -> Bedrock Claude -> insurance claim fields.

    Returns both the claim sub-object AND a payment patch so the caller can
    update payment.amountToBePayed with the patient's true out-of-pocket cost.
    """
    textract_result = {
        "raw_text":   event.get("raw_text", ""),
        "key_values": event.get("key_values", {}),
        "tables":     event.get("tables", []),
    }

    # Validate that the uploaded document is actually an insurance claim.
    classification = bedrock_utils.classify_document_type(textract_result["raw_text"])
    doc_type = classification.get("documentType", "unknown")
    if doc_type != "insuranceClaim":
        found_label = _DOC_TYPE_LABELS.get(doc_type, "an unrecognized document")
        reason = (
            f"Invalid document: expected an insurance claim but received {found_label}. "
            "Please upload the correct file."
        )
        logger.warning("[extract_claim] Wrong document type detected: %s – %s", doc_type, reason)
        return {
            "valid":   False,
            "reason":  reason,
            "claim":   {},
            "payment": {},
        }

    claim = claim_extractor.extract_claim(textract_result)
    return {
        "valid":  True,
        "reason": "",
        "claim":  claim,
        # The claim document authoritatively tells us what the patient owes;
        # surface it so the front-end / state-machine can patch payment too.
        "payment": {
            "amountToBePayed": claim.get("remainingAmountToBePaid", ""),
        },
    }


def _action_extract_medical(event: dict) -> dict:
    """action: extract_medical — Comprehend Medical + Bedrock -> extractedData fields.

    Also surfaces purposeOfVisit when the medical record contains it,
    so the front-end can pre-fill that field for the user to confirm.
    """
    textract_result = {
        "raw_text":   event.get("raw_text", ""),
        "key_values": event.get("key_values", {}),
        "tables":     event.get("tables", []),
    }

    # Validate that the uploaded document is actually a medical record.
    classification = bedrock_utils.classify_document_type(textract_result["raw_text"])
    doc_type = classification.get("documentType", "unknown")
    if doc_type != "medicalRecord":
        found_label = _DOC_TYPE_LABELS.get(doc_type, "an unrecognized document")
        reason = (
            f"Invalid document: expected a medical record but received {found_label}. "
            "Please upload the correct file."
        )
        logger.warning("[extract_medical] Wrong document type detected: %s – %s", doc_type, reason)
        return {
            "valid":          False,
            "reason":         reason,
            "confidence":     0.0,
            "extractedData":  {},
            "purposeOfVisit": "",
        }

    cm_result  = comprehend_medical_utils.analyze_medical_text(textract_result["raw_text"])
    extracted  = medical_extractor.extract_medical_data(textract_result, cm_result)
    confidence = extracted.get("confidence", 0.0)

    # purposeOfVisit lives at review root level, not inside extractedData
    purpose_of_visit = extracted.pop("purposeOfVisit", "")

    return {
        "valid":          True,
        "reason":         "",
        "confidence":     confidence,
        "extractedData":  extracted,
        # Returned separately so the front-end can pre-fill the purposeOfVisit field
        "purposeOfVisit": purpose_of_visit,
    }


def _action_index_review(event: dict) -> dict:
    """
    action: index_review
    ────────────────────
    Invoked asynchronously (InvocationType='Event') after a review is created.

    Steps:
      1. Fetch review, doctor, hospital records from DynamoDB (3 parallel-ish gets)
      2. Build combinedText → Bedrock Titan Embed v2 → 1 024-dim vector
      3. PUT combined document into OpenSearch

    Input event keys: reviewId, doctorId, hospitalId
    """
    review_id   = event["reviewId"]
    doctor_id   = event["doctorId"]
    hospital_id = event["hospitalId"]

    logger.info(
        "index_review start: reviewId=%s doctorId=%s hospitalId=%s",
        review_id, doctor_id, hospital_id,
    )

    # ── 1. Fetch from DynamoDB ─────────────────────────────────────────────
    review_item: dict[str, Any] = {}
    try:
        review_item = table.get_item(Key={"reviewId": review_id}).get("Item") or {}
    except Exception as exc:
        logger.exception("Failed to fetch review %s for indexing", review_id)
        raise

    doctor_item: dict[str, Any] = {}
    try:
        doctor_item = _doctor_table.get_item(Key={"doctorId": doctor_id}).get("Item") or {}
    except Exception as exc:
        logger.warning("Could not fetch doctor %s: %s", doctor_id, exc)

    hospital_item: dict[str, Any] = {}
    try:
        hospital_item = _hospital_table.get_item(Key={"hospitalId": hospital_id}).get("Item") or {}
    except Exception as exc:
        logger.warning("Could not fetch hospital %s: %s", hospital_id, exc)

    # ── 2. Generate embedding ──────────────────────────────────────────────
    combined_text = opensearch_utils._build_combined_text(review_item, doctor_item, hospital_item)
    embedding     = bedrock_utils.generate_embedding(combined_text)

    # ── 3. Index into OpenSearch ───────────────────────────────────────────
    result = opensearch_utils.index_review(
        review_id     = review_id,
        review_item   = review_item,
        doctor_item   = doctor_item,
        hospital_item = hospital_item,
        embedding     = embedding,
    )

    logger.info(
        "index_review complete: reviewId=%s opensearch_result=%s",
        review_id, result.get("result"),
    )
    return {"indexed": True, "reviewId": review_id, "result": result.get("result")}


_ACTION_HANDLERS = {
    "textract_extract":     _action_textract_extract,
    "extract_bill":         _action_extract_bill,
    "extract_claim":        _action_extract_claim,
    "extract_medical":      _action_extract_medical,
    "index_review":         _action_index_review,
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
        expr_attr_values[vk] = _sanitize_for_dynamo(value)

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

    if method == "GET" and path.endswith("/reviews/documents/download"):
        return get_document_download_url_handler(event)

    if method == "GET" and path.endswith("/reviews/documents"):
        return get_user_documents_handler(event)

    if method == "DELETE" and path.endswith("/reviews/documents"):
        return delete_document_handler(event)

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
