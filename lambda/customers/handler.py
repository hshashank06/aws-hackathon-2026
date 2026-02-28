"""
AWS Lambda – Customer CRUD
==========================
Handles the following API Gateway (HTTP API or REST API) proxy events:

  POST   /customers                 → create_customer
  GET    /customers                 → list_customers   (optional ?limit=N&lastKey=<token>)
  GET    /customers/{customerId}    → get_customer
  PUT    /customers/{customerId}    → update_customer
  DELETE /customers/{customerId}    → delete_customer

Environment variables (required):
  TABLE_NAME   – DynamoDB table name  (default: "Customers")
  AWS_REGION   – injected automatically by the Lambda runtime

Customer schema
---------------
  customerId   (PK, String)
  customerName (String)
  email        (String)
  createdAt    (String, ISO-8601 datetime)
  policyId     (String | null)
  gender       (String)
  age          (Number)
  uhid         (String)
  visits       (List of { hospitalId, departmentId, doctorId })
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
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME: str = "customers"
PARTITION_KEY: str = "customerId"

_dynamodb = boto3.resource("dynamodb")
table = _dynamodb.Table(TABLE_NAME)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class DecimalEncoder(json.JSONEncoder):
    """Serialise DynamoDB Decimal values returned by boto3."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            # Return int when there is no fractional part, float otherwise.
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)


def _response(status_code: int, body: Any) -> dict:
    """Build an API Gateway proxy-compatible HTTP response."""
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
    """Safely parse the request body from API Gateway event."""
    raw = event.get("body") or "{}"
    if isinstance(raw, str):
        return json.loads(raw)
    return raw  # Already a dict (Lambda test events)


def _get_customer_id(event: dict) -> str | None:
    """Extract {customerId} from path parameters."""
    path_params = event.get("pathParameters") or {}
    return path_params.get("customerId")


# ---------------------------------------------------------------------------
# CRUD handlers
# ---------------------------------------------------------------------------


def create_customer(event: dict) -> dict:
    """
    POST /customers
    Creates a new customer record.
    Body fields: customerName*, email*, gender*, age*, uhid*,
                 policyId (optional), visits (optional list)
    customerId and createdAt are generated server-side.
    """
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _error(400, "Invalid JSON in request body.")

    # Validate required fields
    required = ["customerName", "email", "gender", "age", "uhid"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return _error(400, f"Missing required fields: {', '.join(missing)}")

    customer_id = f"customer_id_{uuid.uuid4().hex[:5]}"
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    item = {
        PARTITION_KEY: customer_id,
        "customerName": body["customerName"],
        "email": body["email"],
        "gender": body["gender"],
        "age": int(body["age"]),
        "uhid": body["uhid"],
        "policyId": body.get("policyId"),  # nullable
        "visits": body.get("visits", []),
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
            return _error(409, f"Customer '{customer_id}' already exists.")
        logger.exception("DynamoDB put_item failed")
        return _error(500, "Failed to create customer.")

    logger.info("Created customer %s", customer_id)
    return _ok(item, status_code=201)


def get_customer(event: dict) -> dict:
    """
    GET /customers/{customerId}
    Returns a single customer by primary key.
    """
    customer_id = _get_customer_id(event)
    if not customer_id:
        return _error(400, "Missing path parameter: customerId")

    try:
        result = table.get_item(Key={PARTITION_KEY: customer_id})
    except ClientError:
        logger.exception("DynamoDB get_item failed")
        return _error(500, "Failed to retrieve customer.")

    item = result.get("Item")
    if not item:
        return _error(404, f"Customer '{customer_id}' not found.")

    return _ok(item)


def list_customers(event: dict) -> dict:
    """
    GET /customers
    Returns a paginated list of all customers.
    Query params:
      limit   – max items per page (default 20, max 100)
      lastKey – opaque pagination token returned by a previous call
    """
    query_params = event.get("queryStringParameters") or {}

    # Pagination limit
    try:
        limit = min(int(query_params.get("limit", 20)), 100)
    except ValueError:
        limit = 20

    scan_kwargs: dict[str, Any] = {"Limit": limit}

    # Resume from previous page
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
        return _error(500, "Failed to list customers.")

    response_body: dict[str, Any] = {
        "items": result.get("Items", []),
        "count": result.get("Count", 0),
    }

    # Include next-page token only when there are more results
    if "LastEvaluatedKey" in result:
        response_body["lastKey"] = json.dumps(result["LastEvaluatedKey"])

    return _ok(response_body)


def update_customer(event: dict) -> dict:
    """
    PUT /customers/{customerId}
    Partially updates mutable fields of an existing customer.
    Updatable fields: customerName, email, gender, age, policyId, visits, uhid
    """
    customer_id = _get_customer_id(event)
    if not customer_id:
        return _error(400, "Missing path parameter: customerId")

    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _error(400, "Invalid JSON in request body.")

    if not body:
        return _error(400, "Request body must not be empty.")

    # Fields that may be updated (customerId and createdAt are immutable)
    UPDATABLE = {"customerName", "email", "gender", "age", "policyId", "visits", "uhid"}
    updates = {k: v for k, v in body.items() if k in UPDATABLE}

    if not updates:
        return _error(400, f"No updatable fields provided. Allowed: {sorted(UPDATABLE)}")

    # Dynamically build UpdateExpression
    set_expressions = []
    expr_attr_names: dict[str, str] = {}
    expr_attr_values: dict[str, Any] = {}

    for field, value in updates.items():
        placeholder = f"#f_{field}"
        value_key = f":v_{field}"
        set_expressions.append(f"{placeholder} = {value_key}")
        expr_attr_names[placeholder] = field
        if field == "age" and value is not None:
            value = int(value)
        expr_attr_values[value_key] = value

    update_expression = "SET " + ", ".join(set_expressions)
    
    logger.info("Update expression for customer %s: %s", customer_id, update_expression)

    try:
        result = table.update_item(
            Key={PARTITION_KEY: customer_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames={**expr_attr_names, "#pk": PARTITION_KEY},
            ExpressionAttributeValues=expr_attr_values,
            ConditionExpression="attribute_exists(#pk)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "ConditionalCheckFailedException":
            return _error(404, f"Customer '{customer_id}' not found.")
        logger.exception("DynamoDB update_item failed")
        return _error(500, "Failed to update customer.")

    logger.info("Updated customer %s fields: %s", customer_id, list(updates.keys()))
    return _ok(result["Attributes"])


def delete_customer(event: dict) -> dict:
    """
    DELETE /customers/{customerId}
    Deletes a customer record. Returns the deleted item.
    """
    customer_id = _get_customer_id(event)
    if not customer_id:
        return _error(400, "Missing path parameter: customerId")

    try:
        result = table.delete_item(
            Key={PARTITION_KEY: customer_id},
            ConditionExpression="attribute_exists(#pk)",
            ExpressionAttributeNames={"#pk": PARTITION_KEY},
            ReturnValues="ALL_OLD",
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "ConditionalCheckFailedException":
            return _error(404, f"Customer '{customer_id}' not found.")
        logger.exception("DynamoDB delete_item failed")
        return _error(500, "Failed to delete customer.")

    logger.info("Deleted customer %s", customer_id)
    return _ok({"message": f"Customer '{customer_id}' deleted.", "deleted": result.get("Attributes", {})})


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

# Mapping: (HTTP method, has customerId?) → handler function
_ROUTES: dict[tuple[str, bool], Any] = {
    ("POST",   False): create_customer,
    ("GET",    False): list_customers,
    ("GET",    True):  get_customer,
    ("PUT",    True):  update_customer,
    ("DELETE", True):  delete_customer,
}


def lambda_handler(event: dict, context: Any) -> dict:
    """Main Lambda entry point wired to API Gateway proxy integration."""
    method: str = (event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")).upper()
    customer_id = _get_customer_id(event)

    logger.info("Routing %s /customers%s", method, f"/{customer_id}" if customer_id else "")

    handler_fn = _ROUTES.get((method, customer_id is not None))
    if handler_fn is None:
        return _error(405, f"Method '{method}' not allowed on this resource.")

    try:
        return handler_fn(event)
    except Exception:
        logger.exception("Unhandled exception in handler %s", handler_fn.__name__)
        return _error(500, "Internal server error.")
