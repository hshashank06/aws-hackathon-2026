"""
AWS Lambda – AI-Powered Hospital Search
========================================
This Lambda function orchestrates intelligent hospital search by:
1. Invoking AWS Bedrock Agent for AI-powered recommendations
2. Fetching detailed data from multiple API Gateway endpoints
3. Calculating statistics and insurance coverage from reviews
4. Building a comprehensive response for the UI

Routes:
  POST /search  → search_hospitals

Environment variables (required):
  BEDROCK_AGENT_ID       – Bedrock Agent ID (e.g., ASPMAO88W7)
  BEDROCK_AGENT_ALIAS_ID – Agent Alias ID (e.g., FXGJQUGJRJQ)
  BEDROCK_REGION         – AWS region for Bedrock (default: us-east-1)
  API_GATEWAY_BASE_URL   – Base URL for API Gateway endpoints
  
Request Body:
  {
    "query": "best hospital for cardiac surgery",
    "customerId": "customer_123",  // Used as sessionId for agent memory
    "userContext": {
      "insuranceId": "ins_001",    // Optional
      "location": {                // Optional
        "latitude": 28.6139,
        "longitude": 77.2090
      }
    }
  }

Response Format:
  See SEARCH_RESPONSE_FORMAT.md for complete structure
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
import requests
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# Environment variables
BEDROCK_AGENT_ID = os.environ.get("BEDROCK_AGENT_ID", "ASPMAO88W7")
BEDROCK_AGENT_ALIAS_ID = os.environ.get("BEDROCK_AGENT_ALIAS_ID", "AQNFMZGOCZ")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
API_GATEWAY_BASE_URL = os.environ.get(
    "API_GATEWAY_BASE_URL",
    "https://ri8zkgmzlb.execute-api.us-east-1.amazonaws.com"
)
DYNAMODB_REGION = os.environ.get("DYNAMODB_REGION", "eu-north-1")
SEARCH_RESULTS_TABLE = os.environ.get("SEARCH_RESULTS_TABLE", "SearchResults")
LAMBDA_FUNCTION_NAME = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "searchFunction")
LAMBDA_REGION = os.environ.get("AWS_REGION", "us-east-1")  # Lambda's own region

# Initialize AWS clients
bedrock_agent_runtime = boto3.client("bedrock-agent-runtime", region_name=BEDROCK_REGION)
dynamodb = boto3.resource("dynamodb", region_name=DYNAMODB_REGION)
lambda_client = boto3.client("lambda", region_name=LAMBDA_REGION)  # Use Lambda's region, not DynamoDB's
search_results_table = dynamodb.Table(SEARCH_RESULTS_TABLE)

# Constants
MAX_WORKERS = 20  # For parallel API calls
REQUEST_TIMEOUT = 10  # seconds for HTTP requests
AGENT_TIMEOUT = 30  # seconds for Bedrock Agent invocation


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

class DecimalEncoder(json.JSONEncoder):
    """Serialize DynamoDB Decimal values."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)


def _response(status_code: int, body: Any) -> dict:
    """Build API Gateway response."""
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


def _error(status_code: int, message: str, details: dict = None) -> dict:
    error_body = {"success": False, "error": message}
    if details:
        error_body["details"] = details
    return _response(status_code, error_body)


def _parse_body(event: dict) -> dict:
    """Parse request body from API Gateway event."""
    raw = event.get("body") or "{}"
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


# ---------------------------------------------------------------------------
# Bedrock Agent Integration
# ---------------------------------------------------------------------------

def invoke_bedrock_agent(query: str, customer_id: str, max_retries: int = 3) -> dict:
    """
    Invoke AWS Bedrock Agent for AI-powered hospital recommendations.
    Includes retry logic with exponential backoff for timeout/throttling errors.
    
    Args:
        query: User's search query
        customer_id: Customer ID (used as sessionId for conversation memory)
        max_retries: Maximum number of retry attempts (default: 3)
    
    Returns:
        dict: LLM response with aiSummary and hospitals array
    
    Raises:
        Exception: If agent invocation fails after all retries
    """
    session_id = customer_id or f"session_{uuid.uuid4().hex[:12]}"
    
    logger.info(
        "Invoking Bedrock Agent | AgentId=%s | AliasId=%s | SessionId=%s | Query='%s'",
        BEDROCK_AGENT_ID,
        BEDROCK_AGENT_ALIAS_ID,
        session_id,
        query[:100]  # Log first 100 chars
    )
    
    start_time = time.time()
    
    # Retry loop with exponential backoff
    for attempt in range(max_retries):
        try:
            return _invoke_bedrock_agent_once(query, session_id, start_time, attempt + 1)
        
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_msg = e.response["Error"]["Message"]
            
            # Check if error is retryable
            is_retryable = error_code in [
                "dependencyFailedException",
                "ThrottlingException",
                "ServiceUnavailableException",
                "InternalServerException",
                "ModelTimeoutException"
            ]
            
            if is_retryable and attempt < max_retries - 1:
                # Calculate backoff delay: 2^attempt seconds (1s, 2s, 4s)
                backoff_delay = 2 ** attempt
                logger.warning(
                    "Bedrock Agent error (retryable) | Attempt=%d/%d | ErrorCode=%s | RetryIn=%ds",
                    attempt + 1,
                    max_retries,
                    error_code,
                    backoff_delay
                )
                time.sleep(backoff_delay)
                continue  # Retry
            else:
                # Non-retryable error or max retries reached
                logger.error(
                    "Bedrock Agent invocation failed | Attempt=%d/%d | ErrorCode=%s | ErrorMsg=%s",
                    attempt + 1,
                    max_retries,
                    error_code,
                    error_msg
                )
                raise Exception(f"Bedrock Agent error: {error_code} - {error_msg}")
        
        except Exception as e:
            # Non-ClientError exceptions (parsing errors, etc.)
            if attempt < max_retries - 1:
                backoff_delay = 2 ** attempt
                logger.warning(
                    "Bedrock Agent error (unexpected) | Attempt=%d/%d | Error=%s | RetryIn=%ds",
                    attempt + 1,
                    max_retries,
                    str(e),
                    backoff_delay
                )
                time.sleep(backoff_delay)
                continue  # Retry
            else:
                logger.exception("Bedrock Agent invocation failed after all retries")
                raise
    
    # Should never reach here, but just in case
    raise Exception("Bedrock Agent invocation failed after all retries")


def _invoke_bedrock_agent_once(query: str, session_id: str, start_time: float, attempt: int) -> dict:
    """
    Single invocation attempt of Bedrock Agent (internal helper).
    
    Args:
        query: User's search query
        session_id: Session ID for conversation memory
        start_time: Request start time for logging
        attempt: Current attempt number
    
    Returns:
        dict: LLM response with aiSummary and hospitals array
    
    Raises:
        ClientError: If Bedrock API call fails
        Exception: If response parsing fails
    """
    logger.debug("Bedrock Agent invocation attempt | Attempt=%d | SessionId=%s", attempt, session_id)
    
    response = bedrock_agent_runtime.invoke_agent(
        agentId=BEDROCK_AGENT_ID,
        agentAliasId=BEDROCK_AGENT_ALIAS_ID,
        sessionId=session_id,
        inputText=query,
    )
    
    # Properly handle streaming response - collect ALL chunks
    full_response = ""
    chunk_count = 0
    
    # Process all events in the completion stream
    # CRITICAL: Must iterate through ALL events to get complete response
    completion_stream = response.get("completion", [])
    
    for event in completion_stream:
        # Log event type for debugging
        event_type = list(event.keys())[0] if event else "unknown"
        logger.debug("Event received | Type=%s", event_type)
        
        if "chunk" in event:
            chunk = event["chunk"]
            if "bytes" in chunk:
                # Decode bytes and append to full response
                chunk_data = chunk["bytes"].decode("utf-8")
                full_response += chunk_data
                chunk_count += 1
                logger.debug("Chunk %d received | Length=%d | Content=%s", 
                            chunk_count, len(chunk_data), chunk_data[:100])
        
        # Handle other event types that might contain data
        elif "trace" in event:
            logger.debug("Trace event received")
        elif "returnControl" in event:
            logger.debug("ReturnControl event received")
        elif "internalServerException" in event:
            logger.error("InternalServerException in stream")
            raise ClientError(
                {"Error": {"Code": "InternalServerException", "Message": "Bedrock Agent internal server error"}},
                "invoke_agent"
            )
        elif "validationException" in event:
            logger.error("ValidationException in stream")
            raise ClientError(
                {"Error": {"Code": "ValidationException", "Message": "Bedrock Agent validation error"}},
                "invoke_agent"
            )
    
    # Ensure we received some response
    if not full_response:
        logger.error("No response received from Bedrock Agent | ChunkCount=%d", chunk_count)
        raise Exception("Empty response from Bedrock Agent")
    
    elapsed = time.time() - start_time
    logger.info(
        "Bedrock Agent response received | Attempt=%d | Chunks=%d | ResponseLength=%d | Duration=%.2fs",
        attempt,
        chunk_count,
        len(full_response),
        elapsed
    )
    
    # Log full response for debugging (truncated to 3000 chars)
    logger.info("Full Agent response (first 3000 chars): %s", full_response[:3000])
    if len(full_response) > 3000:
        logger.info("Full Agent response (last 500 chars): %s", full_response[-500:])
    
    # Parse JSON response - extract JSON from conversational text
    try:
        # Find the first '{' and extract JSON from there
        json_start = full_response.find('{')
        if json_start == -1:
            logger.error("No JSON object found in response | Response=%s", full_response[:500])
            raise ValueError("No JSON object found in Bedrock Agent response")
        
        # Extract from first '{' to end
        json_str = full_response[json_start:]
        
        # Log if there was text before JSON
        if json_start > 0:
            prefix = full_response[:json_start].strip()
            logger.info("Stripped conversational prefix | Prefix='%s'", prefix[:100])
        
        # Try to fix incomplete JSON by adding missing closing brackets
        json_str_stripped = json_str.strip()
        if not json_str_stripped.endswith('}'):
            logger.warning("JSON appears incomplete | Ends with: '%s'", json_str_stripped[-50:])
            
            # Count opening and closing braces/brackets
            open_braces = json_str_stripped.count('{')
            close_braces = json_str_stripped.count('}')
            open_brackets = json_str_stripped.count('[')
            close_brackets = json_str_stripped.count(']')
            
            logger.info("Brace count | Open={%d} Close={%d} | Open=[%d] Close=[%d]", 
                       open_braces, close_braces, open_brackets, close_brackets)
            
            # Try to complete the JSON by adding missing closures
            fixed_json = json_str_stripped
            
            # Add missing closing brackets/braces
            if close_brackets < open_brackets:
                fixed_json += ']' * (open_brackets - close_brackets)
                logger.info("Added %d closing brackets", open_brackets - close_brackets)
            
            if close_braces < open_braces:
                fixed_json += '}' * (open_braces - close_braces)
                logger.info("Added %d closing braces", open_braces - close_braces)
            
            json_str = fixed_json
            logger.info("Attempted to fix incomplete JSON | NewLength=%d", len(json_str))
        
        llm_data = json.loads(json_str)
        logger.info(
            "LLM response parsed | Attempt=%d | Hospitals=%d | HasSummary=%s",
            attempt,
            len(llm_data.get("hospitals", [])),
            "aiSummary" in llm_data
        )
        return llm_data
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM response as JSON | Error=%s | Response=%s", str(e), full_response[:500])
        logger.error("JSON string that failed to parse (last 500 chars): %s", json_str[-500:] if len(json_str) > 500 else json_str)
        
        # Last resort: try to salvage what we can
        try:
            # Try to find the last complete hospital entry
            last_hospital_end = json_str.rfind('}]')
            if last_hospital_end > 0:
                salvaged_json = json_str[:last_hospital_end + 2] + '}'
                logger.info("Attempting to salvage partial JSON | Length=%d", len(salvaged_json))
                llm_data = json.loads(salvaged_json)
                logger.warning("Successfully salvaged partial response | Hospitals=%d", len(llm_data.get("hospitals", [])))
                return llm_data
        except:
            pass
        
        raise ValueError(f"Invalid JSON response from Bedrock Agent: {str(e)}")


# ---------------------------------------------------------------------------
# API Gateway HTTP Calls
# ---------------------------------------------------------------------------

def fetch_from_api(endpoint: str, resource_type: str, resource_id: str = None) -> dict:
    """
    Fetch data from API Gateway endpoint.
    
    Args:
        endpoint: API endpoint path (e.g., 'hospitals', 'doctors')
        resource_type: Type of resource for logging
        resource_id: Optional resource ID for specific item
    
    Returns:
        dict: API response data
    """
    if resource_id:
        url = f"{API_GATEWAY_BASE_URL}/{endpoint}/{resource_id}"
    else:
        url = f"{API_GATEWAY_BASE_URL}/{endpoint}"
    
    logger.debug("API Request | Type=%s | URL=%s", resource_type, url)
    
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        logger.debug(
            "API Response | Type=%s | Status=%d | DataKeys=%s",
            resource_type,
            response.status_code,
            list(data.keys()) if isinstance(data, dict) else "list"
        )
        
        return data
    
    except requests.exceptions.Timeout:
        logger.error("API request timeout | Type=%s | URL=%s", resource_type, url)
        raise Exception(f"Timeout fetching {resource_type}")
    
    except requests.exceptions.HTTPError as e:
        logger.error(
            "API HTTP error | Type=%s | Status=%d | URL=%s",
            resource_type,
            e.response.status_code,
            url
        )
        raise Exception(f"HTTP {e.response.status_code} fetching {resource_type}")
    
    except Exception as e:
        logger.exception("API request failed | Type=%s | URL=%s", resource_type, url)
        raise


def fetch_reviews(query_params: dict) -> list:
    """
    Fetch reviews with query parameters.
    
    Args:
        query_params: Dict of query parameters (hospitalId, doctorId, etc.)
    
    Returns:
        list: Review items
    """
    params_str = "&".join([f"{k}={v}" for k, v in query_params.items()])
    url = f"{API_GATEWAY_BASE_URL}/reviews?{params_str}&limit=100"
    
    logger.debug("Fetching reviews | Params=%s", query_params)
    
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        items = data.get("items", [])
        logger.debug("Reviews fetched | Count=%d | Params=%s", len(items), query_params)
        
        return items
    
    except Exception as e:
        logger.error("Failed to fetch reviews | Params=%s | Error=%s", query_params, str(e))
        return []  # Return empty list on error, don't fail the whole search


# ---------------------------------------------------------------------------
# Data Enrichment Functions
# ---------------------------------------------------------------------------

def calculate_hospital_stats(reviews: list, hospital_data: dict) -> dict:
    """
    Calculate hospital statistics from reviews.
    
    Args:
        reviews: List of review items for this hospital
        hospital_data: Hospital data from API
    
    Returns:
        dict: Statistics including ratings, costs, wait times
    """
    logger.debug("Calculating hospital stats | HospitalId=%s | ReviewCount=%d", 
                 hospital_data.get("hospitalId"), len(reviews))
    
    if not reviews:
        # Use pre-computed values from hospital table
        return {
            "totalReviews": 0,
            "verifiedReviews": 0,
            "averageRating": hospital_data.get("rating", 0),
            "ratingBreakdown": {
                "serviceQuality": 0,
                "maintenance": 0,
                "foodQuality": 0,
                "cleanliness": 0,
                "staffBehavior": 0,
            },
            "claimApprovalRate": (
                hospital_data.get("totalNumberOfClaimsApproved", 0) / 
                hospital_data.get("totalNumberOfClaims", 1)
            ) if hospital_data.get("totalNumberOfClaims") else 0,
            "averageCost": hospital_data.get("avgCost", 0),
            "averageWaitTime": 3,  # Default
        }
    
    # Calculate from reviews
    verified_reviews = [r for r in reviews if r.get("verified")]
    total_reviews = len(reviews)
    verified_count = len(verified_reviews)
    
    # Extract ratings (assuming hospitalReview contains rating info)
    # This is a simplified calculation - adjust based on actual review structure
    avg_rating = hospital_data.get("rating", 4.0)
    
    stats = {
        "totalReviews": total_reviews,
        "verifiedReviews": verified_count,
        "averageRating": avg_rating,
        "ratingBreakdown": {
            "serviceQuality": avg_rating,
            "maintenance": avg_rating - 0.2,
            "foodQuality": avg_rating - 0.5,
            "cleanliness": avg_rating + 0.1,
            "staffBehavior": avg_rating - 0.1,
        },
        "claimApprovalRate": (
            hospital_data.get("totalNumberOfClaimsApproved", 0) / 
            hospital_data.get("totalNumberOfClaims", 1)
        ) if hospital_data.get("totalNumberOfClaims") else 0,
        "averageCost": hospital_data.get("avgCost", 0),
        "averageWaitTime": 3,
    }
    
    logger.debug("Hospital stats calculated | Stats=%s", stats)
    return stats


def calculate_doctor_stats(reviews: list, doctor_data: dict) -> dict:
    """
    Calculate doctor statistics from reviews.
    
    Args:
        reviews: List of review items for this doctor
        doctor_data: Doctor data from API
    
    Returns:
        dict: Statistics including ratings, success rate
    """
    logger.debug("Calculating doctor stats | DoctorId=%s | ReviewCount=%d",
                 doctor_data.get("doctorId"), len(reviews))
    
    verified_reviews = [r for r in reviews if r.get("verified")]
    avg_rating = doctor_data.get("rating", 4.5)
    
    stats = {
        "totalReviews": len(reviews),
        "verifiedReviews": len(verified_reviews),
        "averageRating": avg_rating,
        "ratingBreakdown": {
            "bedsideManner": avg_rating + 0.1,
            "medicalExpertise": avg_rating + 0.2,
            "communication": avg_rating,
            "waitTime": avg_rating - 0.3,
            "thoroughness": avg_rating + 0.1,
            "followUpCare": avg_rating,
        },
        "successRate": 0.95,  # Default - could be calculated from reviews
        "totalSurgeries": len(reviews),  # Simplified
    }
    
    logger.debug("Doctor stats calculated | Stats=%s", stats)
    return stats


def calculate_insurance_coverage(reviews: list, insurance_id: str, hospital_data: dict) -> dict:
    """
    Calculate insurance coverage estimates from reviews.
    
    Args:
        reviews: List of review items for this hospital
        insurance_id: User's insurance policy ID
        hospital_data: Hospital data
    
    Returns:
        dict: Insurance match information with coverage estimates
    """
    logger.debug(
        "Calculating insurance coverage | HospitalId=%s | InsuranceId=%s | ReviewCount=%d",
        hospital_data.get("hospitalId"),
        insurance_id,
        len(reviews)
    )
    
    # Filter reviews with this insurance
    insurance_reviews = [r for r in reviews if r.get("policyId") == insurance_id]
    
    if not insurance_reviews:
        logger.debug("No reviews found for this insurance | Using hospital defaults")
        # Use hospital-level data
        claim_approval_rate = (
            hospital_data.get("totalNumberOfClaimsApproved", 0) / 
            hospital_data.get("totalNumberOfClaims", 1)
        ) if hospital_data.get("totalNumberOfClaims") else 0.85
        
        avg_cost = hospital_data.get("avgCost", 300000)
        estimated_coverage = avg_cost * 0.9
        estimated_out_of_pocket = avg_cost * 0.1
    else:
        # Calculate from insurance-specific reviews
        approved_claims = sum(1 for r in insurance_reviews if r.get("claim", {}).get("claimAmountApproved"))
        claim_approval_rate = approved_claims / len(insurance_reviews) if insurance_reviews else 0.85
        
        # Calculate average coverage
        total_bills = []
        total_coverage = []
        
        for review in insurance_reviews:
            payment = review.get("payment", {})
            claim = review.get("claim", {})
            
            if payment.get("totalBillAmount"):
                total_bills.append(float(payment["totalBillAmount"]))
            
            if claim.get("claimAmountApproved"):
                total_coverage.append(float(claim["claimAmountApproved"]))
        
        avg_cost = sum(total_bills) / len(total_bills) if total_bills else 300000
        estimated_coverage = sum(total_coverage) / len(total_coverage) if total_coverage else avg_cost * 0.9
        estimated_out_of_pocket = avg_cost - estimated_coverage
    
    result = {
        "isAccepted": True,  # Assuming LLM only returns matching hospitals
        "insuranceCompanyId": insurance_id,
        "claimApprovalRate": claim_approval_rate,
        "estimatedCoverage": int(estimated_coverage),
        "estimatedOutOfPocket": int(estimated_out_of_pocket),
    }
    
    logger.debug("Insurance coverage calculated | Result=%s", result)
    return result


def get_all_hospital_doctors(hospital_data: dict) -> list:
    """
    Fetch all doctors in a hospital from its departments.
    
    Args:
        hospital_data: Hospital data containing departmentIds
    
    Returns:
        list: List of doctor IDs in this hospital
    """
    hospital_id = hospital_data.get("hospitalId")
    department_ids = hospital_data.get("departmentIds", [])
    
    # Parse if it's a JSON string
    if isinstance(department_ids, str):
        try:
            department_ids = json.loads(department_ids)
        except:
            department_ids = []
    
    logger.debug(
        "Fetching all doctors for hospital | HospitalId=%s | DepartmentCount=%d",
        hospital_id,
        len(department_ids)
    )
    
    all_doctor_ids = []
    
    for dept_id in department_ids:
        try:
            dept_data = fetch_from_api("departments", "Department", dept_id)
            doctor_ids = dept_data.get("listOfDoctorIds", [])
            
            # Parse if it's a JSON string
            if isinstance(doctor_ids, str):
                try:
                    doctor_ids = json.loads(doctor_ids)
                except:
                    doctor_ids = []
            
            all_doctor_ids.extend(doctor_ids)
            logger.debug(
                "Department doctors fetched | DeptId=%s | DoctorCount=%d",
                dept_id,
                len(doctor_ids)
            )
        except Exception as e:
            logger.warning("Failed to fetch department | DeptId=%s | Error=%s", dept_id, str(e))
            continue
    
    # Remove duplicates
    unique_doctor_ids = list(set(all_doctor_ids))
    logger.info(
        "All hospital doctors collected | HospitalId=%s | TotalDoctors=%d",
        hospital_id,
        len(unique_doctor_ids)
    )
    
    return unique_doctor_ids


# ---------------------------------------------------------------------------
# DynamoDB Operations
# ---------------------------------------------------------------------------

def save_search_status(search_id: str, status: str, query: str = None, customer_id: str = None, 
                       results: dict = None, error: str = None, partial_results: dict = None,
                       progress: int = None) -> None:
    """
    Save search status to DynamoDB.
    
    Args:
        search_id: Unique search identifier
        status: "processing" | "complete" | "error"
        query: User's search query (optional)
        customer_id: Customer ID (optional)
        results: Search results (optional, for complete status)
        error: Error message (optional, for error status)
        partial_results: Partial results for progressive loading (optional)
        progress: Progress percentage 0-100 (optional)
    """
    try:
        item = {
            "searchId": search_id,
            "status": status,
            "updatedAt": int(time.time()),
        }
        
        if query:
            item["query"] = query
        if customer_id:
            item["customerId"] = customer_id
        if results:
            item["results"] = results
        if error:
            item["error"] = error
        if partial_results:
            item["partialResults"] = partial_results
        if progress is not None:
            item["progress"] = progress
        if status == "processing":
            item["createdAt"] = int(time.time())
            # Set TTL to 1 hour from now
            item["ttl"] = int(time.time()) + 3600
        
        search_results_table.put_item(Item=item)
        logger.info("Search status saved | SearchId=%s | Status=%s | Progress=%s", 
                   search_id, status, progress if progress else "N/A")
    
    except Exception as e:
        logger.error("Failed to save search status | SearchId=%s | Error=%s", search_id, str(e))
        # Don't raise - this is not critical


def get_search_status(search_id: str) -> dict:
    """
    Get search status from DynamoDB.
    
    Args:
        search_id: Unique search identifier
    
    Returns:
        dict: Search record or None if not found
    """
    try:
        response = search_results_table.get_item(Key={"searchId": search_id})
        item = response.get("Item")
        
        if item:
            logger.info("Search status retrieved | SearchId=%s | Status=%s", search_id, item.get("status"))
        else:
            logger.warning("Search not found | SearchId=%s", search_id)
        
        return item
    
    except Exception as e:
        logger.error("Failed to get search status | SearchId=%s | Error=%s", search_id, str(e))
        return None


def invoke_async_search(search_id: str, query: str, customer_id: str, user_context: dict, context=None) -> None:
    """
    Invoke Lambda function asynchronously to process search in background.
    
    Args:
        search_id: Unique search identifier
        query: User's search query
        customer_id: Customer ID
        user_context: User context (insurance, location, etc.)
        context: Lambda context (optional, to get function name)
    """
    try:
        # Get function name from context or environment variable
        function_name = LAMBDA_FUNCTION_NAME
        if context and hasattr(context, 'function_name'):
            function_name = context.function_name
        
        payload = {
            "asyncSearch": True,
            "searchId": search_id,
            "query": query,
            "customerId": customer_id,
            "userContext": user_context,
        }
        
        logger.info("Invoking async search | FunctionName=%s | SearchId=%s", function_name, search_id)
        
        lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="Event",  # Async invocation
            Payload=json.dumps(payload),
        )
        
        logger.info("Async search invoked | SearchId=%s", search_id)
    
    except Exception as e:
        logger.error("Failed to invoke async search | SearchId=%s | Error=%s", search_id, str(e))
        # Update status to error
        save_search_status(search_id, "error", error=f"Failed to start background processing: {str(e)}")


# ---------------------------------------------------------------------------
# Main Search Orchestration
# ---------------------------------------------------------------------------

def enrich_hospital_data(
    hospital_llm: dict,
    hospital_data: dict,
    reviews: list,
    insurance_id: str = None
) -> dict:
    """
    Enrich hospital data with statistics and AI insights.
    
    Args:
        hospital_llm: Hospital data from LLM (with AI review)
        hospital_data: Hospital data from API
        reviews: Reviews for this hospital
        insurance_id: User's insurance ID (optional)
    
    Returns:
        dict: Enriched hospital data matching SEARCH_RESPONSE_FORMAT
    """
    hospital_id = hospital_data.get("hospitalId")
    logger.info("Enriching hospital data | HospitalId=%s", hospital_id)
    
    # Calculate statistics
    stats = calculate_hospital_stats(reviews, hospital_data)
    
    # Parse services if it's a JSON string
    services = hospital_data.get("services", [])
    if isinstance(services, str):
        try:
            services = json.loads(services)
        except:
            services = []
    
    # Parse location
    location_str = hospital_data.get("location", "0,0")
    try:
        lat, lon = map(float, location_str.split(","))
    except:
        lat, lon = 0.0, 0.0
    
    # Build enriched hospital object
    enriched = {
        "hospitalId": hospital_id,
        "hospitalName": hospital_data.get("hospitalName", ""),
        "services": services,
        "location": {
            "latitude": lat,
            "longitude": lon,
            "distance": None,  # TODO: Calculate if user location provided
        },
        "address": hospital_data.get("address", ""),
        "phoneNumber": hospital_data.get("phoneNumber", ""),
        "description": hospital_data.get("description", ""),
        "aiInsights": {
            "matchScore": 90,  # Default - could be extracted from LLM
            "explanation": hospital_llm.get("hospitalAIReview", ""),
            "keyStrengths": [],  # TODO: Extract from AI review
            "considerations": [],
        },
        "stats": stats,
        "insuranceInfo": {
            "acceptedCompanies": [],  # TODO: Fetch insurance companies
            "userInsuranceMatch": None,
        },
        "relevantDepartments": [],  # TODO: Fetch departments
        "topDoctors": [],  # Will be populated separately
        "costEstimates": {},  # TODO: Build from hospital data
        "trustIndicators": {
            "verified": True,
            "trustScore": 85,
            "verificationBadge": "gold",
            "accreditations": [],
            "documentVerificationRate": 0.9,
            "fakeReviewsBlocked": 0,
        },
        "facilities": [],  # TODO: Extract from hospital data
        "images": [],
    }
    
    # Add insurance match if user has insurance
    if insurance_id:
        enriched["insuranceInfo"]["userInsuranceMatch"] = calculate_insurance_coverage(
            reviews, insurance_id, hospital_data
        )
    
    logger.debug("Hospital enrichment complete | HospitalId=%s", hospital_id)
    return enriched


def enrich_doctor_data(
    doctor_llm: dict,
    doctor_data: dict,
    reviews: list
) -> dict:
    """
    Enrich doctor data with statistics and AI insights.
    
    Args:
        doctor_llm: Doctor data from LLM (with AI review)
        doctor_data: Doctor data from API
        reviews: Reviews for this doctor
    
    Returns:
        dict: Enriched doctor data matching SEARCH_RESPONSE_FORMAT
    """
    doctor_id = doctor_data.get("doctorId")
    logger.debug("Enriching doctor data | DoctorId=%s", doctor_id)
    
    # Calculate statistics
    stats = calculate_doctor_stats(reviews, doctor_data)
    
    # Build enriched doctor object
    enriched = {
        "doctorId": doctor_id,
        "doctorName": doctor_data.get("doctorName", ""),
        "specialty": "General",  # TODO: Extract from department or doctor data
        "experience": f"{doctor_data.get('yearsOfExperience', 10)}+ years",
        "about": doctor_data.get("about", ""),
        "aiReview": {
            "summary": doctor_llm.get("doctorAIReview", ""),
            "keyHighlights": [],  # TODO: Extract from AI review
        },
        "stats": stats,
        "recentReviews": [],  # TODO: Format recent reviews
        "availability": {
            "nextAvailableSlot": datetime.now(timezone.utc).isoformat(),
            "averageWaitTime": 5,
            "acceptingNewPatients": True,
        },
    }
    
    logger.debug("Doctor enrichment complete | DoctorId=%s", doctor_id)
    return enriched


def search_hospitals(event: dict, context=None) -> dict:
    """
    Main search handler - orchestrates the entire search process.
    
    Two modes:
    1. Sync mode (initial request): Returns searchId immediately, processes in background
    2. Async mode (background): Processes search and stores results in DynamoDB
    
    Process:
    1. Parse request and validate
    2. Generate searchId and return immediately (sync mode)
    3. Invoke self asynchronously to process search (async mode)
    4. Invoke Bedrock Agent for AI recommendations
    5. Fetch detailed data from API Gateway (parallel)
    6. Calculate statistics from reviews
    7. Store results in DynamoDB
    
    Args:
        event: API Gateway event or async invocation payload
    
    Returns:
        dict: API Gateway response (sync) or None (async)
    """
    # Check if this is an async background invocation
    is_async = event.get("asyncSearch", False)
    
    if is_async:
        # Background processing mode
        return process_search_async(event)
    else:
        # Initial request mode - return immediately
        return initiate_search_sync(event, context)


def initiate_search_sync(event: dict, context=None) -> dict:
    """
    Handle initial search request - return searchId immediately.
    
    Args:
        event: API Gateway event
    
    Returns:
        dict: API Gateway response with searchId and status
    """
    request_id = event.get("requestContext", {}).get("requestId", uuid.uuid4().hex[:12])
    logger.info("=" * 80)
    logger.info("SEARCH REQUEST (SYNC) | RequestId=%s", request_id)
    logger.info("=" * 80)
    
    try:
        # Parse request
        body = _parse_body(event)
        query = body.get("query", "").strip()
        customer_id = body.get("customerId", "").strip()
        user_context = body.get("userContext", {})
        
        logger.info(
            "Request parsed | Query='%s' | CustomerId=%s",
            query[:100],
            customer_id or "None"
        )
        
        # Validate required fields
        if not query:
            logger.warning("Missing required field: query")
            return _error(400, "Missing required field: query")
        
        # Generate searchId
        search_id = f"search_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Save initial status to DynamoDB
        save_search_status(search_id, "processing", query=query, customer_id=customer_id)
        
        # Invoke async processing
        invoke_async_search(search_id, query, customer_id, user_context, context)
        
        # Return immediately
        response_body = {
            "success": True,
            "searchId": search_id,
            "status": "processing",
            "message": "Search is being processed. Use the searchId to check status.",
            "estimatedTime": "30-40 seconds",
        }
        
        logger.info("Search initiated | SearchId=%s", search_id)
        logger.info("=" * 80)
        
        return _ok(response_body, status_code=202)  # 202 Accepted
    
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return _error(400, "Invalid JSON in request body")
    
    except Exception as e:
        logger.exception("Failed to initiate search | RequestId=%s", request_id)
        return _error(
            500,
            "An unexpected error occurred. Please try again.",
            {"code": "INTERNAL_ERROR"}
        )


def process_search_async(event: dict) -> None:
    """
    Process search in background (async mode).
    
    Args:
        event: Async invocation payload with searchId, query, etc.
    """
    search_id = event.get("searchId")
    query = event.get("query")
    customer_id = event.get("customerId")
    user_context = event.get("userContext", {})
    insurance_id = user_context.get("insuranceId")
    
    logger.info("=" * 80)
    logger.info("SEARCH REQUEST (ASYNC) | SearchId=%s", search_id)
    logger.info("=" * 80)
    
    start_time = time.time()
    
    try:
        logger.info(
            "Request parsed | Query='%s' | CustomerId=%s | InsuranceId=%s",
            query[:100] if query else "None",
            customer_id or "None",
            insurance_id or "None"
        )
        
        # Validate required fields
        if not query:
            logger.warning("Missing required field: query")
            save_search_status(search_id, "error", error="Missing required field: query")
            return
        
        # Step 1: Invoke Bedrock Agent
        logger.info("STEP 1: Invoking Bedrock Agent")
        try:
            llm_response = invoke_bedrock_agent(query, customer_id)
        except Exception as e:
            logger.error("Bedrock Agent invocation failed | Error=%s", str(e))
            save_search_status(
                search_id,
                "error",
                error="Search service temporarily unavailable. Please try again."
            )
            return  # Exit async function
        
        # Validate LLM response
        if not llm_response.get("hospitals"):
            logger.warning("LLM returned no hospitals")
            save_search_status(
                search_id,
                "error",
                error="No hospitals found matching your criteria. Try different keywords."
            )
            return  # Exit async function
        
        ai_summary = llm_response.get("aiSummary", "")
        hospitals_llm = llm_response.get("hospitals", [])
        
        logger.info("LLM response validated | HospitalCount=%d", len(hospitals_llm))
        
        # Save partial results #1: AI Summary + Hospital IDs (Progress: 30%)
        partial_results_1 = {
            "aiSummary": ai_summary,
            "hospitalCount": len(hospitals_llm),
            "hospitalIds": [h["hospitalId"] for h in hospitals_llm],
            "stage": "llm_complete"
        }
        save_search_status(search_id, "processing", partial_results=partial_results_1, progress=30)


        # Step 2: Extract IDs from LLM response
        logger.info("STEP 2: Extracting IDs from LLM response")
        hospital_ids = [h["hospitalId"] for h in hospitals_llm]
        
        # Extract doctor IDs from LLM recommendations
        llm_doctor_ids = []
        for h in hospitals_llm:
            for d in h.get("doctors", []):
                doctor_id = d["doctorId"]
                llm_doctor_ids.append(doctor_id)
                logger.info("Extracted doctor ID from LLM | DoctorId=%s | HospitalId=%s", doctor_id, h["hospitalId"])
        
        logger.info(
            "IDs extracted | Hospitals=%d | LLM-recommended Doctors=%d",
            len(hospital_ids),
            len(llm_doctor_ids)
        )
        
        # Step 3: Fetch data in parallel
        logger.info("STEP 3: Fetching data from API Gateway (parallel)")
        
        hospitals_data = {}
        doctors_data = {}
        hospital_reviews = {}
        doctor_reviews = {}
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {}
            
            # Submit hospital fetch tasks
            for hospital_id in hospital_ids:
                future = executor.submit(fetch_from_api, "hospitals", "Hospital", hospital_id)
                futures[future] = ("hospital", hospital_id)
            
            # Submit doctor fetch tasks (LLM-recommended doctors)
            for doctor_id in llm_doctor_ids:
                future = executor.submit(fetch_from_api, "doctors", "Doctor", doctor_id)
                futures[future] = ("doctor", doctor_id)
            
            # Submit review fetch tasks
            for hospital_id in hospital_ids:
                future = executor.submit(fetch_reviews, {"hospitalId": hospital_id})
                futures[future] = ("hospital_reviews", hospital_id)
            
            for doctor_id in llm_doctor_ids:
                future = executor.submit(fetch_reviews, {"doctorId": doctor_id})
                futures[future] = ("doctor_reviews", doctor_id)
            
            # Collect results
            completed = 0
            total = len(futures)
            
            for future in as_completed(futures):
                completed += 1
                task_type, resource_id = futures[future]
                
                try:
                    result = future.result()
                    
                    if task_type == "hospital":
                        hospitals_data[resource_id] = result
                    elif task_type == "doctor":
                        doctors_data[resource_id] = result
                    elif task_type == "hospital_reviews":
                        hospital_reviews[resource_id] = result
                    elif task_type == "doctor_reviews":
                        doctor_reviews[resource_id] = result
                    
                    logger.debug(
                        "Task completed | Progress=%d/%d | Type=%s | ResourceId=%s",
                        completed,
                        total,
                        task_type,
                        resource_id
                    )
                
                except Exception as e:
                    logger.error(
                        "Task failed | Type=%s | ResourceId=%s | Error=%s",
                        task_type,
                        resource_id,
                        str(e)
                    )
                    # Log additional details for doctor fetch failures
                    if task_type == "doctor":
                        logger.error(
                            "Doctor fetch failed - check if doctor exists in DynamoDB | DoctorId=%s | URL=%s/doctors/%s",
                            resource_id,
                            API_GATEWAY_BASE_URL,
                            resource_id
                        )
        
        logger.info(
            "Data fetching complete | Hospitals=%d | Doctors=%d | HospitalReviews=%d | DoctorReviews=%d",
            len(hospitals_data),
            len(doctors_data),
            len(hospital_reviews),
            len(doctor_reviews)
        )
        
        # Save partial results #2: Basic hospital info (Progress: 60%)
        partial_hospitals = []
        for hospital_llm in hospitals_llm:
            hospital_id = hospital_llm["hospitalId"]
            hospital_data = hospitals_data.get(hospital_id)
            if hospital_data:
                # Parse location
                location_str = hospital_data.get("location", "0,0")
                try:
                    lat, lon = map(float, location_str.split(","))
                except:
                    lat, lon = 0.0, 0.0
                
                partial_hospitals.append({
                    "hospitalId": hospital_id,
                    "hospitalName": hospital_data.get("hospitalName", ""),
                    "address": hospital_data.get("address", ""),
                    "phoneNumber": hospital_data.get("phoneNumber", ""),
                    "location": {"latitude": lat, "longitude": lon},
                    "aiReview": hospital_llm.get("hospitalAIReview", ""),
                })
        
        partial_results_2 = {
            "aiSummary": ai_summary,
            "hospitals": partial_hospitals,
            "stage": "basic_data_complete"
        }
        save_search_status(search_id, "processing", partial_results=partial_results_2, progress=60)


        # Step 4: Build enriched response
        logger.info("STEP 4: Building enriched response")
        
        enriched_hospitals = []
        
        for hospital_llm in hospitals_llm:
            hospital_id = hospital_llm["hospitalId"]
            
            # Get hospital data
            hospital_data = hospitals_data.get(hospital_id)
            if not hospital_data:
                logger.warning("Hospital data not found | HospitalId=%s", hospital_id)
                continue
            
            # Get reviews for this hospital
            reviews = hospital_reviews.get(hospital_id, [])
            
            # Enrich hospital data
            enriched_hospital = enrich_hospital_data(
                hospital_llm,
                hospital_data,
                reviews,
                insurance_id
            )
            
            # Add LLM-recommended doctors
            top_doctors = []
            for doctor_llm in hospital_llm.get("doctors", []):
                doctor_id = doctor_llm["doctorId"]
                doctor_data = doctors_data.get(doctor_id)
                
                if doctor_data:
                    doctor_reviews_list = doctor_reviews.get(doctor_id, [])
                    enriched_doctor = enrich_doctor_data(
                        doctor_llm,
                        doctor_data,
                        doctor_reviews_list
                    )
                    top_doctors.append(enriched_doctor)
                    logger.info("Doctor enriched successfully | DoctorId=%s | HospitalId=%s", doctor_id, hospital_id)
                else:
                    logger.warning(
                        "Doctor data not found - skipping | DoctorId=%s | HospitalId=%s | Reason=API fetch failed or returned 404",
                        doctor_id,
                        hospital_id
                    )
            
            enriched_hospital["topDoctors"] = top_doctors
            
            logger.info(
                "Hospital enriched | HospitalId=%s | TopDoctors=%d",
                hospital_id,
                len(top_doctors)
            )
            
            enriched_hospitals.append(enriched_hospital)
        
        # Build final response
        elapsed = time.time() - start_time
        
        response_body = {
            "success": True,
            "cached": False,
            "responseTime": f"{int(elapsed * 1000)}ms",
            "userIntent": {
                "category": "general_search",
                "keywords": query.split()[:5],  # First 5 words
                "insuranceRequired": bool(insurance_id),
                "procedureType": "general",
            },
            "results": {
                "totalMatches": len(enriched_hospitals),
                "hospitals": enriched_hospitals,
            },
            "metadata": {
                "searchId": search_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "aiModel": "bedrock-agent",
                "databaseVersion": "v1.0.0",
                "totalHospitalsInDatabase": 29,
                "totalDoctorsInDatabase": 976,
            },
        }
        
        # Save results to DynamoDB
        save_search_status(search_id, "complete", results=response_body)
        
        logger.info("=" * 80)
        logger.info(
            "SEARCH REQUEST COMPLETE (ASYNC) | SearchId=%s | Duration=%.2fs | Hospitals=%d",
            search_id,
            elapsed,
            len(enriched_hospitals)
        )
        logger.info("=" * 80)
    
    except Exception as e:
        elapsed = time.time() - start_time
        logger.exception(
            "Search request failed (async) | SearchId=%s | Duration=%.2fs",
            search_id,
            elapsed
        )
        save_search_status(
            search_id,
            "error",
            error="An unexpected error occurred during search processing."
        )


def get_search_results(event: dict) -> dict:
    """
    Get search results by searchId.
    
    Args:
        event: API Gateway event with searchId in path
    
    Returns:
        dict: API Gateway response with search status and results
    """
    try:
        # Extract searchId from path parameters
        search_id = event.get("pathParameters", {}).get("searchId")
        
        if not search_id:
            return _error(400, "Missing searchId in path")
        
        logger.info("Getting search results | SearchId=%s", search_id)
        
        # Get from DynamoDB
        item = get_search_status(search_id)
        
        if not item:
            return _error(404, "Search not found", {"searchId": search_id})
        
        status = item.get("status")
        
        if status == "processing":
            response_data = {
                "success": True,
                "searchId": search_id,
                "status": "processing",
                "progress": item.get("progress", 0),
                "message": "Search is still being processed. Please check again in a few seconds.",
            }
            
            # Include partial results if available
            partial_results = item.get("partialResults")
            if partial_results:
                response_data["partialResults"] = partial_results
            
            return _ok(response_data)
        
        elif status == "complete":
            # Return the full results
            results = item.get("results", {})
            return _ok(results)
        
        elif status == "error":
            error_msg = item.get("error", "An error occurred during search processing")
            return _error(500, error_msg, {"searchId": search_id})
        
        else:
            return _error(500, "Unknown search status", {"searchId": search_id, "status": status})
    
    except Exception as e:
        logger.exception("Failed to get search results")
        return _error(500, "Failed to retrieve search results")


# ---------------------------------------------------------------------------
# Lambda Handler
# ---------------------------------------------------------------------------

def lambda_handler(event: dict, context: Any) -> dict:
    """
    Main Lambda entry point for API Gateway integration.
    
    Routes:
      POST /search           → initiate_search_sync (returns searchId immediately)
      GET  /search/{searchId} → get_search_results (poll for results)
      Async invocation       → process_search_async (background processing)
    
    Args:
        event: API Gateway event or async invocation payload
        context: Lambda context
    
    Returns:
        dict: API Gateway response or None (async)
    """
    # Check if this is an async invocation
    if event.get("asyncSearch"):
        search_hospitals(event)
        return None  # No response for async invocations
    
    method = (
        event.get("httpMethod") 
        or event.get("requestContext", {}).get("http", {}).get("method", "")
    ).upper()
    
    path = (
        event.get("path", "")
        or event.get("requestContext", {}).get("http", {}).get("path", "")
    ).rstrip("/").lower()
    
    logger.info("Lambda invoked | Method=%s | Path=%s", method, path)
    
    # Route to handlers
    if method == "POST" and path.endswith("/search"):
        return search_hospitals(event, context)
    
    elif method == "GET" and "/search/" in path:
        return get_search_results(event)
    
    # Method not allowed
    logger.warning("Method not allowed | Method=%s | Path=%s", method, path)
    return _error(405, f"Method '{method}' not allowed on path '{path}'")
