"""
AWS Lambda - Search Invoker Function
=====================================
This Lambda function is triggered by AppSync mutation 'initiateSearch'.
It generates a searchId, saves initial status to DynamoDB, and invokes
WorkerLambda asynchronously to process the search.

Environment Variables:
  WORKER_FUNCTION_NAME   - Name of WorkerLambda function
  DYNAMODB_TABLE_NAME    - SearchResults table name
  DYNAMODB_REGION        - DynamoDB region

IAM Permissions Required:
  - lambda:InvokeFunction on WorkerLambda
  - dynamodb:PutItem on SearchResults table
"""

import json
import boto3
import os
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
lambda_client = boto3.client("lambda")
dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("DYNAMODB_REGION", "eu-north-1"))
search_results_table = dynamodb.Table(os.environ.get("DYNAMODB_TABLE_NAME", "SearchResults"))

# Constants
WORKER_FUNCTION_NAME = os.environ.get("WORKER_FUNCTION_NAME", "Worker")
SEARCH_RESULT_TTL_HOURS = 5


def convert_floats_to_decimal(obj):
    """Convert floats to Decimal for DynamoDB compatibility."""
    if isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj


def lambda_handler(event, context):
    """
    AppSync resolver for initiateSearch mutation.
    
    Args:
        event: AppSync event with arguments
        context: Lambda context
    
    Returns:
        dict: {searchId, status}
    """
    try:
        logger.info(f"InvokerLambda started | Event: {json.dumps(event)}")
        
        # Extract arguments from AppSync event
        arguments = event.get("arguments", {})
        query = arguments.get("query")
        customer_id = arguments.get("customerId", "anonymous")
        user_location = arguments.get("userLocation")
        
        # Validate query
        if not query or not query.strip():
            logger.error("Missing or empty query")
            raise ValueError("Query is required")
        
        # Generate searchId
        request_id = context.request_id[:12] if context and hasattr(context, 'request_id') else uuid.uuid4().hex[:12]
        search_id = f"search_{int(time.time())}_{request_id}"
        
        logger.info(f"Generated searchId: {search_id}")
        
        # Save initial status to DynamoDB
        ttl = int(time.time()) + (SEARCH_RESULT_TTL_HOURS * 3600)
        item = {
            "searchId": search_id,
            "status": "processing",
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "ttl": ttl
        }
        
        # Add user location if provided
        if user_location:
            item["userLocation"] = convert_floats_to_decimal(user_location)
            logger.info(f"User location: {user_location}")
        
        search_results_table.put_item(Item=item)
        logger.info(f"Saved initial status to DynamoDB | SearchId: {search_id}")
        
        # Prepare payload for WorkerLambda
        payload = {
            "searchId": search_id,
            "query": query,
            "customerId": customer_id,
            "userLocation": user_location
        }
        
        # Invoke WorkerLambda asynchronously
        lambda_client.invoke(
            FunctionName=WORKER_FUNCTION_NAME,
            InvocationType="Event",  # Async invocation
            Payload=json.dumps(payload)
        )
        
        logger.info(f"Invoked WorkerLambda asynchronously | SearchId: {search_id}")
        
        # Return immediately
        return {
            "searchId": search_id,
            "status": "processing"
        }
    
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise
    
    except Exception as e:
        logger.exception(f"InvokerLambda failed: {str(e)}")
        raise
