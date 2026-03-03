"""
AWS Lambda â€“ InsuranceCompany CRUD
====================================
Handles the following API Gateway (HTTP API or REST API) proxy events:

  POST   /insurance-companies                           â†’ create_insurance_company
  GET    /insurance-companies                           â†’ list_insurance_companies  (optional ?limit=N&lastKey=<token>)
  GET    /insurance-companies/{insuranceCompanyId}      â†’ get_insurance_company
  PUT    /insurance-companies/{insuranceCompanyId}      â†’ update_insurance_company
  DELETE /insurance-companies/{insuranceCompanyId}      â†’ delete_insurance_company

Environment variables (required):
  TABLE_NAME   â€“ DynamoDB table name  (default: "InsuranceCompany")
  AWS_REGION   â€“ injected automatically by the Lambda runtime

InsuranceCompany schema
-----------------------
  insuranceCompanyId    (PK, String)
  insuranceCompanyName  (String)
  description           (String)
  services              (String)
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

TABLE_NAME: str = os.environ.get("TABLE_NAME", "InsuranceCompany")
DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "eu-north-1")
PARTITION_KEY: str = "insuranceCompanyId"

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


def _get_company_id(event: dict) -> str | None:
    path_params = event.get("pathParameters") or {}
    return path_params.get("insuranceCompanyId")


# ---------------------------------------------------------------------------
# CRUD handlers
# ---------------------------------------------------------------------------


def create_insurance_company(event: dict) -> dict:
    """
    POST /insurance-companies
    Creates a new insurance company record.
    Body fields: insuranceCompanyName*, description (optional), services (optional)
    insuranceCompanyId and createdAt are generated server-side.
    """
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _error(400, "Invalid JSON in request body.")

    required = ["insuranceCompanyName"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return _error(400, f"Missing required fields: {', '.join(missing)}")

    company_id = f"insurancecomp_{uuid.uuid4().hex[:10]}"
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    item = {
        PARTITION_KEY: company_id,
        "insuranceCompanyName": body["insuranceCompanyName"],
        "description": body.get("description", ""),
        "services": body.get("services", ""),
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
            return _error(409, f"Insurance company '{company_id}' already exists.")
        logger.exception("DynamoDB put_item failed")
        return _error(500, "Failed to create insurance company.")

    logger.info("Created insurance company %s", company_id)
    return _ok(item, status_code=201)


def get_insurance_company(event: dict) -> dict:
    """
    GET /insurance-companies/{insuranceCompanyId}
    Returns a single insurance company by primary key.
    """
    company_id = _get_company_id(event)
    if not company_id:
        return _error(400, "Missing path parameter: insuranceCompanyId")

    try:
        result = table.get_item(Key={PARTITION_KEY: company_id})
    except ClientError:
        logger.exception("DynamoDB get_item failed")
        return _error(500, "Failed to retrieve insurance company.")

    item = result.get("Item")
    if not item:
        return _error(404, f"Insurance company '{company_id}' not found.")

    return _ok(item)


def list_insurance_companies(event: dict) -> dict:
    """
    GET /insurance-companies
    Returns a paginated list of all insurance companies.
    Query params:
      limit   â€“ max items per page (default 20, max 100)
      lastKey â€“ opaque pagination token returned by a previous call
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
        return _error(500, "Failed to list insurance companies.")

    response_body: dict[str, Any] = {
        "items": result.get("Items", []),
        "count": result.get("Count", 0),
    }

    if "LastEvaluatedKey" in result:
        response_body["lastKey"] = json.dumps(result["LastEvaluatedKey"])

    return _ok(response_body)


def update_insurance_company(event: dict) -> dict:
    """
    PUT /insurance-companies/{insuranceCompanyId}
    Partially updates mutable fields of an existing insurance company.
    Updatable fields: insuranceCompanyName, description, services
    """
    company_id = _get_company_id(event)
    if not company_id:
        return _error(400, "Missing path parameter: insuranceCompanyId")

    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _error(400, "Invalid JSON in request body.")

    if not body:
        return _error(400, "Request body must not be empty.")

    UPDATABLE = {"insuranceCompanyName", "description", "services"}
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

    logger.info("Update expression for insurance company %s: %s", company_id, update_expression)

    try:
        result = table.update_item(
            Key={PARTITION_KEY: company_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames={**expr_attr_names, "#pk": PARTITION_KEY},
            ExpressionAttributeValues=expr_attr_values,
            ConditionExpression="attribute_exists(#pk)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "ConditionalCheckFailedException":
            return _error(404, f"Insurance company '{company_id}' not found.")
        logger.exception("DynamoDB update_item failed")
        return _error(500, "Failed to update insurance company.")

    logger.info("Updated insurance company %s fields: %s", company_id, list(updates.keys()))
    return _ok(result["Attributes"])


def delete_insurance_company(event: dict) -> dict:
    """
    DELETE /insurance-companies/{insuranceCompanyId}
    Deletes an insurance company record. Returns the deleted item.
    """
    company_id = _get_company_id(event)
    if not company_id:
        return _error(400, "Missing path parameter: insuranceCompanyId")

    try:
        result = table.delete_item(
            Key={PARTITION_KEY: company_id},
            ConditionExpression="attribute_exists(#pk)",
            ExpressionAttributeNames={"#pk": PARTITION_KEY},
            ReturnValues="ALL_OLD",
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "ConditionalCheckFailedException":
            return _error(404, f"Insurance company '{company_id}' not found.")
        logger.exception("DynamoDB delete_item failed")
        return _error(500, "Failed to delete insurance company.")

    logger.info("Deleted insurance company %s", company_id)
    return _ok({"message": f"Insurance company '{company_id}' deleted.", "deleted": result.get("Attributes", {})})


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

_ROUTES: dict[tuple[str, bool], Any] = {
    ("POST",   False): create_insurance_company,
    ("GET",    False): list_insurance_companies,
    ("GET",    True):  get_insurance_company,
    ("PUT",    True):  update_insurance_company,
    ("DELETE", True):  delete_insurance_company,
}


def lambda_handler(event: dict, context: Any) -> dict:
    """Main Lambda entry point wired to API Gateway proxy integration."""
    method: str = (event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")).upper()
    company_id = _get_company_id(event)

    logger.info("Routing %s /insurance-companies%s", method, f"/{company_id}" if company_id else "")

    handler_fn = _ROUTES.get((method, company_id is not None))
    if handler_fn is None:
        return _error(405, f"Method '{method}' not allowed on this resource.")

    try:
        return handler_fn(event)
    except Exception:
        logger.exception("Unhandled exception in handler %s", handler_fn.__name__)
        return _error(500, "Internal server error.")

