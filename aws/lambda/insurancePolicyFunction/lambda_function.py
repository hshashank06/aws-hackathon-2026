"""
AWS Lambda – InsurancePolicy CRUD
====================================
Handles the following API Gateway (HTTP API or REST API) proxy events:

  POST   /insurance-policies                    → create_policy
  GET    /insurance-policies                    → list_policies  (optional ?limit=N&lastKey=<token>&companyId=<id>)
  GET    /insurance-policies/{policyId}         → get_policy
  PUT    /insurance-policies/{policyId}         → update_policy
  DELETE /insurance-policies/{policyId}         → delete_policy

Environment variables (required):
  TABLE_NAME   – DynamoDB table name  (default: "InsurancePolicy")
  AWS_REGION   – injected automatically by the Lambda runtime

InsurancePolicy schema
----------------------
  policyId    (PK, String)
  companyId   (String, FK → InsuranceCompany)
  about       (String, markdown description of plan)
  createdAt   (String, ISO-8601 datetime)
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

TABLE_NAME: str = os.environ.get("TABLE_NAME", "InsurancePolicy")
PARTITION_KEY: str = "policyId"

_dynamodb = boto3.resource("dynamodb")
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


def _get_policy_id(event: dict) -> str | None:
    path_params = event.get("pathParameters") or {}
    return path_params.get("policyId")


# ---------------------------------------------------------------------------
# CRUD handlers
# ---------------------------------------------------------------------------


def create_policy(event: dict) -> dict:
    """
    POST /insurance-policies
    Creates a new insurance policy record.
    Body fields: companyId*, about (optional)
    policyId and createdAt are generated server-side.
    """
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _error(400, "Invalid JSON in request body.")

    required = ["companyId"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return _error(400, f"Missing required fields: {', '.join(missing)}")

    policy_id = f"{body['companyId']}_policy_{uuid.uuid4().hex[:10]}"
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    item = {
        PARTITION_KEY: policy_id,
        "companyId": body["companyId"],
        "about": body.get("about", ""),
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
            return _error(409, f"Policy '{policy_id}' already exists.")
        logger.exception("DynamoDB put_item failed")
        return _error(500, "Failed to create policy.")

    logger.info("Created policy %s", policy_id)
    return _ok(item, status_code=201)


def get_policy(event: dict) -> dict:
    """
    GET /insurance-policies/{policyId}
    Returns a single policy by primary key.
    """
    policy_id = _get_policy_id(event)
    if not policy_id:
        return _error(400, "Missing path parameter: policyId")

    try:
        result = table.get_item(Key={PARTITION_KEY: policy_id})
    except ClientError:
        logger.exception("DynamoDB get_item failed")
        return _error(500, "Failed to retrieve policy.")

    item = result.get("Item")
    if not item:
        return _error(404, f"Policy '{policy_id}' not found.")

    return _ok(item)


def list_policies(event: dict) -> dict:
    """
    GET /insurance-policies
    Returns a paginated list of policies.
    Query params:
      limit     – max items per page (default 20, max 100)
      lastKey   – opaque pagination token returned by a previous call
      companyId – optional filter by owning insurance company
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

    company_id_filter = query_params.get("companyId")
    if company_id_filter:
        scan_kwargs["FilterExpression"] = Attr("companyId").eq(company_id_filter)

    try:
        result = table.scan(**scan_kwargs)
    except ClientError:
        logger.exception("DynamoDB scan failed")
        return _error(500, "Failed to list policies.")

    response_body: dict[str, Any] = {
        "items": result.get("Items", []),
        "count": result.get("Count", 0),
    }

    if "LastEvaluatedKey" in result:
        response_body["lastKey"] = json.dumps(result["LastEvaluatedKey"])

    return _ok(response_body)


def update_policy(event: dict) -> dict:
    """
    PUT /insurance-policies/{policyId}
    Partially updates mutable fields of an existing policy.
    Updatable fields: companyId, about
    """
    policy_id = _get_policy_id(event)
    if not policy_id:
        return _error(400, "Missing path parameter: policyId")

    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _error(400, "Invalid JSON in request body.")

    if not body:
        return _error(400, "Request body must not be empty.")

    UPDATABLE = {"companyId", "about"}
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

    logger.info("Update expression for policy %s: %s", policy_id, update_expression)

    try:
        result = table.update_item(
            Key={PARTITION_KEY: policy_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames={**expr_attr_names, "#pk": PARTITION_KEY},
            ExpressionAttributeValues=expr_attr_values,
            ConditionExpression="attribute_exists(#pk)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "ConditionalCheckFailedException":
            return _error(404, f"Policy '{policy_id}' not found.")
        logger.exception("DynamoDB update_item failed")
        return _error(500, "Failed to update policy.")

    logger.info("Updated policy %s fields: %s", policy_id, list(updates.keys()))
    return _ok(result["Attributes"])


def delete_policy(event: dict) -> dict:
    """
    DELETE /insurance-policies/{policyId}
    Deletes a policy record. Returns the deleted item.
    """
    policy_id = _get_policy_id(event)
    if not policy_id:
        return _error(400, "Missing path parameter: policyId")

    try:
        result = table.delete_item(
            Key={PARTITION_KEY: policy_id},
            ConditionExpression="attribute_exists(#pk)",
            ExpressionAttributeNames={"#pk": PARTITION_KEY},
            ReturnValues="ALL_OLD",
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "ConditionalCheckFailedException":
            return _error(404, f"Policy '{policy_id}' not found.")
        logger.exception("DynamoDB delete_item failed")
        return _error(500, "Failed to delete policy.")

    logger.info("Deleted policy %s", policy_id)
    return _ok({"message": f"Policy '{policy_id}' deleted.", "deleted": result.get("Attributes", {})})


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

_ROUTES: dict[tuple[str, bool], Any] = {
    ("POST",   False): create_policy,
    ("GET",    False): list_policies,
    ("GET",    True):  get_policy,
    ("PUT",    True):  update_policy,
    ("DELETE", True):  delete_policy,
}


def lambda_handler(event: dict, context: Any) -> dict:
    """Main Lambda entry point wired to API Gateway proxy integration."""
    method: str = (event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")).upper()
    policy_id = _get_policy_id(event)

    logger.info("Routing %s /insurance-policies%s", method, f"/{policy_id}" if policy_id else "")

    handler_fn = _ROUTES.get((method, policy_id is not None))
    if handler_fn is None:
        return _error(405, f"Method '{method}' not allowed on this resource.")

    try:
        return handler_fn(event)
    except Exception:
        logger.exception("Unhandled exception in handler %s", handler_fn.__name__)
        return _error(500, "Internal server error.")
