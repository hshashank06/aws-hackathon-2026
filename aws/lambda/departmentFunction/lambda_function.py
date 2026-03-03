"""
AWS Lambda â€“ Department CRUD
=============================
Handles the following API Gateway (HTTP API or REST API) proxy events:

  POST   /departments                   â†’ create_department
  GET    /departments                   â†’ list_departments  (optional ?limit=N&lastKey=<token>&hospitalId=<id>)
  GET    /departments/{departmentId}    â†’ get_department
  PUT    /departments/{departmentId}    â†’ update_department
  DELETE /departments/{departmentId}    â†’ delete_department

Environment variables (required):
  TABLE_NAME   â€“ DynamoDB table name  (default: "Department")
  AWS_REGION   â€“ injected automatically by the Lambda runtime

Department schema
-----------------
  departmentId          (PK, String)
  departmentName        (String)
  departmentDescription (String)
  hospitalId            (String)
  listOfDoctorIds       (List of String)
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
from boto3.dynamodb.conditions import Attr

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME: str = os.environ.get("TABLE_NAME", "Department")
DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "eu-north-1")
PARTITION_KEY: str = "departmentId"

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


def _get_department_id(event: dict) -> str | None:
    path_params = event.get("pathParameters") or {}
    return path_params.get("departmentId")


# ---------------------------------------------------------------------------
# CRUD handlers
# ---------------------------------------------------------------------------


def create_department(event: dict) -> dict:
    """
    POST /departments
    Creates a new department record.
    Body fields: departmentName*, hospitalId*, departmentDescription (optional), listOfDoctorIds (optional)
    departmentId and createdAt are generated server-side.
    """
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _error(400, "Invalid JSON in request body.")

    required = ["departmentName", "hospitalId"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return _error(400, f"Missing required fields: {', '.join(missing)}")

    department_id = f"department_id_{uuid.uuid4().hex[:5]}"
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    item = {
        PARTITION_KEY: department_id,
        "departmentName": body["departmentName"],
        "hospitalId": body["hospitalId"],
        "departmentDescription": body.get("departmentDescription", ""),
        "listOfDoctorIds": body.get("listOfDoctorIds", []),
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
            return _error(409, f"Department '{department_id}' already exists.")
        logger.exception("DynamoDB put_item failed")
        return _error(500, "Failed to create department.")

    logger.info("Created department %s", department_id)
    return _ok(item, status_code=201)


def get_department(event: dict) -> dict:
    """
    GET /departments/{departmentId}
    Returns a single department by primary key.
    """
    department_id = _get_department_id(event)
    if not department_id:
        return _error(400, "Missing path parameter: departmentId")

    try:
        result = table.get_item(Key={PARTITION_KEY: department_id})
    except ClientError:
        logger.exception("DynamoDB get_item failed")
        return _error(500, "Failed to retrieve department.")

    item = result.get("Item")
    if not item:
        return _error(404, f"Department '{department_id}' not found.")

    return _ok(item)


def list_departments(event: dict) -> dict:
    """
    GET /departments
    Returns a paginated list of departments.
    Query params:
      limit      â€“ max items per page (default 20, max 100)
      lastKey    â€“ opaque pagination token returned by a previous call
      hospitalId â€“ optional filter by hospitalId
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

    hospital_id_filter = query_params.get("hospitalId")
    if hospital_id_filter:
        scan_kwargs["FilterExpression"] = Attr("hospitalId").eq(hospital_id_filter)

    try:
        result = table.scan(**scan_kwargs)
    except ClientError:
        logger.exception("DynamoDB scan failed")
        return _error(500, "Failed to list departments.")

    response_body: dict[str, Any] = {
        "items": result.get("Items", []),
        "count": result.get("Count", 0),
    }

    if "LastEvaluatedKey" in result:
        response_body["lastKey"] = json.dumps(result["LastEvaluatedKey"])

    return _ok(response_body)


def update_department(event: dict) -> dict:
    """
    PUT /departments/{departmentId}
    Partially updates mutable fields of an existing department.
    Updatable fields: departmentName, departmentDescription, hospitalId, listOfDoctorIds
    """
    department_id = _get_department_id(event)
    if not department_id:
        return _error(400, "Missing path parameter: departmentId")

    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _error(400, "Invalid JSON in request body.")

    if not body:
        return _error(400, "Request body must not be empty.")

    UPDATABLE = {"departmentName", "departmentDescription", "hospitalId", "listOfDoctorIds"}
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

    logger.info("Update expression for department %s: %s", department_id, update_expression)

    try:
        result = table.update_item(
            Key={PARTITION_KEY: department_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames={**expr_attr_names, "#pk": PARTITION_KEY},
            ExpressionAttributeValues=expr_attr_values,
            ConditionExpression="attribute_exists(#pk)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "ConditionalCheckFailedException":
            return _error(404, f"Department '{department_id}' not found.")
        logger.exception("DynamoDB update_item failed")
        return _error(500, "Failed to update department.")

    logger.info("Updated department %s fields: %s", department_id, list(updates.keys()))
    return _ok(result["Attributes"])


def delete_department(event: dict) -> dict:
    """
    DELETE /departments/{departmentId}
    Deletes a department record. Returns the deleted item.
    """
    department_id = _get_department_id(event)
    if not department_id:
        return _error(400, "Missing path parameter: departmentId")

    try:
        result = table.delete_item(
            Key={PARTITION_KEY: department_id},
            ConditionExpression="attribute_exists(#pk)",
            ExpressionAttributeNames={"#pk": PARTITION_KEY},
            ReturnValues="ALL_OLD",
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "ConditionalCheckFailedException":
            return _error(404, f"Department '{department_id}' not found.")
        logger.exception("DynamoDB delete_item failed")
        return _error(500, "Failed to delete department.")

    logger.info("Deleted department %s", department_id)
    return _ok({"message": f"Department '{department_id}' deleted.", "deleted": result.get("Attributes", {})})


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

_ROUTES: dict[tuple[str, bool], Any] = {
    ("POST",   False): create_department,
    ("GET",    False): list_departments,
    ("GET",    True):  get_department,
    ("PUT",    True):  update_department,
    ("DELETE", True):  delete_department,
}


def lambda_handler(event: dict, context: Any) -> dict:
    """Main Lambda entry point wired to API Gateway proxy integration."""
    method: str = (event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")).upper()
    department_id = _get_department_id(event)

    logger.info("Routing %s /departments%s", method, f"/{department_id}" if department_id else "")

    handler_fn = _ROUTES.get((method, department_id is not None))
    if handler_fn is None:
        return _error(405, f"Method '{method}' not allowed on this resource.")

    try:
        return handler_fn(event)
    except Exception:
        logger.exception("Unhandled exception in handler %s", handler_fn.__name__)
        return _error(500, "Internal server error.")

