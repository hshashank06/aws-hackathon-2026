"""
AWS Lambda – Hospital CRUD
===========================
Handles the following API Gateway (HTTP API or REST API) proxy events:

  POST   /hospitals               → create_hospital
  GET    /hospitals               → list_hospitals   (optional ?limit=N&lastKey=<token>)
  GET    /hospitals/{hospitalId}  → get_hospital
  PUT    /hospitals/{hospitalId}  → update_hospital
  DELETE /hospitals/{hospitalId}  → delete_hospital

Environment variables (required):
  TABLE_NAME   – DynamoDB table name  (default: "Hospital")
  AWS_REGION   – injected automatically by the Lambda runtime

Hospital schema
---------------
  hospitalId            (PK, String)
  hospitalName          (String)
  address               (String)
  location              (String, "lat, lon")
  phoneNumber           (String)
  services              (List of String)
  departmentIds         (List of String)
  insuranceCompanyIds   (List of String)
  createdAt             (String, ISO-8601 datetime)
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

TABLE_NAME:       str = os.environ.get("TABLE_NAME",       "Hospital")
DYNAMODB_REGION:  str = os.environ.get("DYNAMODB_REGION",  "eu-north-1")
PARTITION_KEY:    str = "hospitalId"

_dynamodb = boto3.resource("dynamodb", region_name=DYNAMODB_REGION)
table = _dynamodb.Table(TABLE_NAME)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class DecimalEncoder(json.JSONEncoder):
    """Serialise DynamoDB Decimal values returned by boto3."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        if isinstance(obj, set):
            return list(obj)  # Convert sets to lists for JSON serialization
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


def _get_hospital_id(event: dict) -> str | None:
    path_params = event.get("pathParameters") or {}
    return path_params.get("hospitalId")


# ---------------------------------------------------------------------------
# CRUD handlers
# ---------------------------------------------------------------------------


def create_hospital(event: dict) -> dict:
    """
    POST /hospitals
    Creates a new hospital record.
    Body fields: hospitalName*, address*, phoneNumber*,
                 location (optional), services (optional list),
                 departmentIds (optional list), insuranceCompanyIds (optional list)
    hospitalId and createdAt are generated server-side.
    """
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _error(400, "Invalid JSON in request body.")

    required = ["hospitalName", "address", "phoneNumber"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return _error(400, f"Missing required fields: {', '.join(missing)}")

    hospital_id = f"hospital_id_{uuid.uuid4().hex[:5]}"
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    item = {
        PARTITION_KEY: hospital_id,
        "hospitalName": body["hospitalName"],
        "address": body["address"],
        "phoneNumber": body["phoneNumber"],
        "location": body.get("location", ""),
        "services": body.get("services", []),
        "departmentIds": body.get("departmentIds", []),
        "insuranceCompanyIds": body.get("insuranceCompanyIds", []),
        "createdAt": created_at,
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
            return _error(409, f"Hospital '{hospital_id}' already exists.")
        logger.exception("DynamoDB put_item failed")
        return _error(500, "Failed to create hospital.")

    logger.info("Created hospital %s", hospital_id)
    return _ok(item, status_code=201)


def get_hospital(event: dict) -> dict:
    """
    GET /hospitals/{hospitalId}
    Returns a single hospital by primary key.
    """
    hospital_id = _get_hospital_id(event)
    if not hospital_id:
        return _error(400, "Missing path parameter: hospitalId")

    try:
        result = table.get_item(Key={PARTITION_KEY: hospital_id})
    except ClientError as e:
        logger.exception("DynamoDB get_item failed | HospitalId=%s | Error=%s", hospital_id, str(e))
        return _error(500, "Failed to retrieve hospital.")
    except Exception as e:
        logger.exception("Unexpected error in get_hospital | HospitalId=%s | Error=%s", hospital_id, str(e))
        return _error(500, "Internal server error.")

    item = result.get("Item")
    if not item:
        return _error(404, f"Hospital '{hospital_id}' not found.")

    # Ensure insuranceCoverage field exists with default value if missing
    if "insuranceCoverage" not in item:
        item["insuranceCoverage"] = 0
        logger.warning("Hospital missing insuranceCoverage field, defaulting to 0 | HospitalId=%s", hospital_id)

    return _ok(item)


def list_hospitals(event: dict) -> dict:
    """
    GET /hospitals
    Returns a paginated list of all hospitals.
    Query params:
      limit   – max items per page (default 20, max 100)
      lastKey – opaque pagination token returned by a previous call
    """
    query_params = event.get("queryStringParameters") or {}

    try:
        limit = min(int(query_params.get("limit", 20)), 100)
    except ValueError:
        limit = 20

    scan_kwargs: dict[str, Any] = {"Limit": limit}

    last_key_raw = query_params.get("lastKey")
    if last_key_raw:
        try:
            exclusive_start = json.loads(last_key_raw)
            scan_kwargs["ExclusiveStartKey"] = exclusive_start
        except (json.JSONDecodeError, TypeError):
            return _error(400, "Invalid lastKey token.")

    try:
        result = table.scan(**scan_kwargs)
    except ClientError:
        logger.exception("DynamoDB scan failed")
        return _error(500, "Failed to list hospitals.")

    response_body: dict[str, Any] = {
        "items": result.get("Items", []),
        "count": result.get("Count", 0),
    }

    if "LastEvaluatedKey" in result:
        response_body["lastKey"] = json.dumps(result["LastEvaluatedKey"])

    return _ok(response_body)


def update_hospital(event: dict) -> dict:
    """
    PUT /hospitals/{hospitalId}
    Partially updates mutable fields of an existing hospital.
    Updatable fields: hospitalName, address, phoneNumber, location,
                      services, departmentIds, insuranceCompanyIds
    """
    hospital_id = _get_hospital_id(event)
    if not hospital_id:
        return _error(400, "Missing path parameter: hospitalId")

    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _error(400, "Invalid JSON in request body.")

    if not body:
        return _error(400, "Request body must not be empty.")

    UPDATABLE = {
        "hospitalName", "address", "phoneNumber", "location",
        "services", "departmentIds", "insuranceCompanyIds",
    }
    updates = {k: v for k, v in body.items() if k in UPDATABLE}

    if not updates:
        return _error(400, f"No updatable fields provided. Allowed: {sorted(UPDATABLE)}")

    set_expressions = []
    expr_attr_names: dict[str, str] = {}
    expr_attr_values: dict[str, Any] = {}

    for field, value in updates.items():
        placeholder = f"#f_{field}"
        value_key = f":v_{field}"
        set_expressions.append(f"{placeholder} = {value_key}")
        expr_attr_names[placeholder] = field
        expr_attr_values[value_key] = value

    update_expression = "SET " + ", ".join(set_expressions)

    logger.info("Update expression for hospital %s: %s", hospital_id, update_expression)

    try:
        result = table.update_item(
            Key={PARTITION_KEY: hospital_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames={**expr_attr_names, "#pk": PARTITION_KEY},
            ExpressionAttributeValues=expr_attr_values,
            ConditionExpression="attribute_exists(#pk)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "ConditionalCheckFailedException":
            return _error(404, f"Hospital '{hospital_id}' not found.")
        logger.exception("DynamoDB update_item failed")
        return _error(500, "Failed to update hospital.")

    logger.info("Updated hospital %s fields: %s", hospital_id, list(updates.keys()))
    return _ok(result["Attributes"])


def delete_hospital(event: dict) -> dict:
    """
    DELETE /hospitals/{hospitalId}
    Deletes a hospital record. Returns the deleted item.
    """
    hospital_id = _get_hospital_id(event)
    if not hospital_id:
        return _error(400, "Missing path parameter: hospitalId")

    try:
        result = table.delete_item(
            Key={PARTITION_KEY: hospital_id},
            ConditionExpression="attribute_exists(#pk)",
            ExpressionAttributeNames={"#pk": PARTITION_KEY},
            ReturnValues="ALL_OLD",
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "ConditionalCheckFailedException":
            return _error(404, f"Hospital '{hospital_id}' not found.")
        logger.exception("DynamoDB delete_item failed")
        return _error(500, "Failed to delete hospital.")

    logger.info("Deleted hospital %s", hospital_id)
    return _ok({"message": f"Hospital '{hospital_id}' deleted.", "deleted": result.get("Attributes", {})})


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

_ROUTES: dict[tuple[str, bool], Any] = {
    ("POST",   False): create_hospital,
    ("GET",    False): list_hospitals,
    ("GET",    True):  get_hospital,
    ("PUT",    True):  update_hospital,
    ("DELETE", True):  delete_hospital,
}


def lambda_handler(event: dict, context: Any) -> dict:
    """Main Lambda entry point wired to API Gateway proxy integration."""
    method: str = (event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")).upper()
    hospital_id = _get_hospital_id(event)

    logger.info("Routing %s /hospitals%s", method, f"/{hospital_id}" if hospital_id else "")

    handler_fn = _ROUTES.get((method, hospital_id is not None))
    if handler_fn is None:
        return _error(405, f"Method '{method}' not allowed on this resource.")

    try:
        return handler_fn(event)
    except Exception:
        logger.exception("Unhandled exception in handler %s", handler_fn.__name__)
        return _error(500, "Internal server error.")
