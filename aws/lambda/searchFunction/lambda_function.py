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
BEDROCK_AGENT_ALIAS_ID = os.environ.get("BEDROCK_AGENT_ALIAS_ID", "TOUEUHIO1O")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
API_GATEWAY_BASE_URL = os.environ.get(
    "API_GATEWAY_BASE_URL",
    "https://ri8zkgmzlb.execute-api.us-east-1.amazonaws.com"
)
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "SearchResults")
DYNAMODB_REGION = os.environ.get("DYNAMODB_REGION", "eu-north-1")

# Initialize AWS clients
bedrock_agent_runtime = boto3.client("bedrock-agent-runtime", region_name=BEDROCK_REGION)
dynamodb = boto3.resource("dynamodb", region_name=DYNAMODB_REGION)
search_results_table = dynamodb.Table(DYNAMODB_TABLE_NAME)
lambda_client = boto3.client("lambda", region_name=os.environ.get("AWS_REGION", "us-east-1"))

# Constants
MAX_WORKERS = 20  # For parallel API calls
REQUEST_TIMEOUT = 10  # seconds for HTTP requests
AGENT_TIMEOUT = 30  # seconds for Bedrock Agent invocation
LLM_MAX_RETRIES = 3  # Maximum retries for LLM invocation
SEARCH_RESULT_TTL_HOURS = 5  # Search results expire after 5 hours


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


def convert_floats_to_decimal(obj: Any) -> Any:
    """
    Recursively convert all float values to Decimal for DynamoDB compatibility.
    
    Args:
        obj: Object to convert (dict, list, or primitive)
    
    Returns:
        Object with floats converted to Decimal
    """
    if isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj


def deserialize_dynamodb_json(obj: Any) -> Any:
    """
    Recursively deserialize DynamoDB JSON format to Python types.
    Handles: {"S": "value"}, {"N": "123"}, {"L": [...]}, {"M": {...}}, {"NULL": true}
    
    Args:
        obj: Object in DynamoDB JSON format
    
    Returns:
        Deserialized Python object
    """
    if isinstance(obj, dict):
        # Check if this is a DynamoDB type descriptor
        if len(obj) == 1:
            type_key = list(obj.keys())[0]
            value = obj[type_key]
            
            if type_key == "S":  # String
                return value
            elif type_key == "N":  # Number
                try:
                    # Try int first, then float
                    if "." in value:
                        return float(value)
                    return int(value)
                except:
                    return value
            elif type_key == "L":  # List
                return [deserialize_dynamodb_json(item) for item in value]
            elif type_key == "M":  # Map
                return {k: deserialize_dynamodb_json(v) for k, v in value.items()}
            elif type_key == "NULL":  # Null
                return None
            elif type_key == "BOOL":  # Boolean
                return value
        
        # Regular dict - recurse into values
        return {k: deserialize_dynamodb_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [deserialize_dynamodb_json(item) for item in obj]
    else:
        return obj


def save_search_results(search_id: str, status: str, llm_response: dict = None, error: str = None) -> None:
    """
    Save search results to DynamoDB.
    
    Args:
        search_id: Unique search identifier
        status: Search status ("processing", "complete", "error")
        llm_response: Raw LLM response (optional)
        error: Error message if status is "error" (optional)
    """
    try:
        # Calculate TTL (5 hours from now)
        ttl = int(time.time()) + (SEARCH_RESULT_TTL_HOURS * 3600)
        
        item = {
            "searchId": search_id,
            "status": status,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "ttl": ttl
        }
        
        if llm_response:
            # Convert floats to Decimal for DynamoDB
            item["llmResponse"] = convert_floats_to_decimal(llm_response)
        
        if error:
            item["error"] = error
        
        search_results_table.put_item(Item=item)
        logger.info("Search results saved | SearchId=%s | Status=%s", search_id, status)
    
    except Exception as e:
        logger.error("Failed to save search results | SearchId=%s | Error=%s", search_id, str(e))
        raise


def get_search_results(search_id: str) -> dict:
    """
    Get search results from DynamoDB.
    
    Args:
        search_id: Unique search identifier
    
    Returns:
        dict: Search results item
    """
    try:
        response = search_results_table.get_item(
            Key={"searchId": search_id},
            ConsistentRead=True
        )
        
        if "Item" not in response:
            logger.warning("Search results not found | SearchId=%s", search_id)
            return None
        
        item = response["Item"]
        
        # Deserialize llmResponse if it's in DynamoDB JSON format
        if "llmResponse" in item:
            llm_response = item["llmResponse"]
            # Check if it's in DynamoDB format (has type descriptors like {"S": "..."})
            if isinstance(llm_response, dict) and any(k in llm_response for k in ["S", "N", "L", "M", "NULL", "BOOL"]):
                logger.info("Deserializing DynamoDB JSON format | SearchId=%s", search_id)
                item["llmResponse"] = deserialize_dynamodb_json(llm_response)
        
        return item
    
    except Exception as e:
        logger.error("Failed to get search results | SearchId=%s | Error=%s", search_id, str(e))
        raise


# ---------------------------------------------------------------------------
# Bedrock Agent Integration
# ---------------------------------------------------------------------------

def invoke_bedrock_agent(query: str, customer_id: str, max_retries: int = LLM_MAX_RETRIES) -> dict:
    """
    Invoke AWS Bedrock Agent for AI-powered hospital recommendations with retry logic.
    
    Args:
        query: User's search query
        customer_id: Customer ID (used as sessionId for conversation memory)
        max_retries: Maximum number of retry attempts
    
    Returns:
        dict: LLM response with aiSummary and hospitals array
    
    Raises:
        Exception: If agent invocation fails after all retries
    """
    session_id = customer_id or f"session_{uuid.uuid4().hex[:12]}"
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "Invoking Bedrock Agent | Attempt=%d/%d | AgentId=%s | AliasId=%s | SessionId=%s | Query='%s'",
                attempt,
                max_retries,
                BEDROCK_AGENT_ID,
                BEDROCK_AGENT_ALIAS_ID,
                session_id,
                query[:100]
            )
            
            start_time = time.time()
            
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
                    raise Exception("Bedrock Agent internal server error")
                elif "validationException" in event:
                    logger.error("ValidationException in stream")
                    raise Exception("Bedrock Agent validation error")
            
            # Ensure we received some response
            if not full_response:
                logger.error("No response received from Bedrock Agent | ChunkCount=%d", chunk_count)
                raise Exception("Empty response from Bedrock Agent")
            
            elapsed = time.time() - start_time
            logger.info(
                "Bedrock Agent response received | Chunks=%d | ResponseLength=%d | Duration=%.2fs",
                chunk_count,
                len(full_response),
                elapsed
            )
            
            # Log full response for debugging (truncated to 3000 chars)
            logger.info("Full Agent response (first 3000 chars): %s", full_response[:3000])
            if len(full_response) > 3000:
                logger.info("Full Agent response (last 500 chars): %s", full_response[-500:])
            
            # Parse JSON response - extract JSON from conversational text
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
            
            # Check if JSON is complete (ends with '}')
            json_str_stripped = json_str.strip()
            if not json_str_stripped.endswith('}'):
                logger.warning("JSON appears incomplete | Ends with: '%s'", json_str_stripped[-50:])
                # Try to find the last complete JSON object
                last_brace = json_str_stripped.rfind('}')
                if last_brace > 0:
                    json_str = json_str_stripped[:last_brace + 1]
                    logger.info("Truncated to last complete brace | NewLength=%d", len(json_str))
            
            llm_data = json.loads(json_str)
            logger.info(
                "LLM response parsed successfully | Attempt=%d | Hospitals=%d | HasSummary=%s",
                attempt,
                len(llm_data.get("hospitals", [])),
                "aiSummary" in llm_data
            )
            return llm_data
        
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON | Attempt=%d | Error=%s | Response=%s", attempt, str(e), full_response[:500])
            logger.error("JSON string that failed to parse (last 500 chars): %s", json_str[-500:] if len(json_str) > 500 else json_str)
            if attempt < max_retries:
                logger.info("Retrying LLM invocation | Attempt=%d/%d", attempt + 1, max_retries)
                time.sleep(1)  # Wait 1 second before retry
                continue
            raise ValueError(f"Invalid JSON response from Bedrock Agent after {max_retries} attempts: {str(e)}")
        
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_msg = e.response["Error"]["Message"]
            logger.error(
                "Bedrock Agent invocation failed | Attempt=%d | ErrorCode=%s | ErrorMsg=%s",
                attempt,
                error_code,
                error_msg
            )
            if attempt < max_retries:
                logger.info("Retrying LLM invocation | Attempt=%d/%d", attempt + 1, max_retries)
                time.sleep(1)  # Wait 1 second before retry
                continue
            raise Exception(f"Bedrock Agent error after {max_retries} attempts: {error_code} - {error_msg}")
        
        except Exception as e:
            logger.error("Unexpected error invoking Bedrock Agent | Attempt=%d | Error=%s", attempt, str(e))
            if attempt < max_retries:
                logger.info("Retrying LLM invocation | Attempt=%d/%d", attempt + 1, max_retries)
                time.sleep(1)  # Wait 1 second before retry
                continue
            logger.exception("All retry attempts exhausted")
            raise


# ---------------------------------------------------------------------------
# Async Search Processing
# ---------------------------------------------------------------------------

def process_search_async(search_id: str, query: str, customer_id: str, insurance_id: str = None):
    """
    Process search asynchronously in background thread.
    This function invokes LLM and stores the raw LLM response in DynamoDB.
    
    Args:
        search_id: Unique search identifier
        query: User's search query
        customer_id: Customer ID
        insurance_id: User's insurance ID (optional)
    """
    try:
        logger.info("Starting async search processing | SearchId=%s", search_id)
        
        # Step 1: Invoke Bedrock Agent with retries
        logger.info("STEP 1: Invoking Bedrock Agent with retries")
        try:
            llm_response = invoke_bedrock_agent(query, customer_id)
        except Exception as e:
            logger.error("LLM invocation failed after all retries | SearchId=%s | Error=%s", search_id, str(e))
            save_search_results(search_id, "error", error=f"Failed to process search: {str(e)}")
            return
        
        # Validate LLM response
        if not llm_response.get("hospitals"):
            logger.warning("LLM returned no hospitals | SearchId=%s", search_id)
            save_search_results(search_id, "complete", llm_response=llm_response)
            return
        
        logger.info("LLM response validated | SearchId=%s | HospitalCount=%d", search_id, len(llm_response.get("hospitals", [])))
        
        # Step 2: Store raw LLM response in DynamoDB
        logger.info("STEP 2: Storing LLM response in DynamoDB | SearchId=%s", search_id)
        save_search_results(search_id, "complete", llm_response=llm_response)
        
        logger.info("Async search processing complete | SearchId=%s", search_id)
    
    except Exception as e:
        logger.exception("Async search processing failed | SearchId=%s", search_id)
        save_search_results(search_id, "error", error=f"Internal error: {str(e)}")


def build_enriched_hospital(hospital_llm: dict, hospital_data: dict, reviews: list, insurance_id: str = None) -> dict:
    """
    Build enriched hospital object for UI.
    
    Args:
        hospital_llm: Hospital data from LLM
        hospital_data: Hospital data from API
        reviews: Hospital reviews from API
        insurance_id: User's insurance ID (optional)
    
    Returns:
        dict: Enriched hospital object
    """
    
    def clean_currency_value(value) -> int:
        """
        Clean currency value by removing symbols and converting to int.
        Handles: ₹427123, $1000, 1000, "₹427123", etc.
        """
        if value is None:
            return 0
        
        # Convert to string if not already
        value_str = str(value)
        
        # Remove currency symbols and whitespace
        cleaned = value_str.replace("₹", "").replace("$", "").replace(",", "").strip()
        
        # Try to convert to int
        try:
            return int(float(cleaned))
        except (ValueError, TypeError):
            return 0
    
    hospital_id = hospital_data.get("hospitalId")
    
    # Parse services
    services = hospital_data.get("services", [])
    if isinstance(services, str):
        try:
            services = json.loads(services)
        except:
            services = []
    
    # Extract location from address
    address = hospital_data.get("address", "")
    # Simple city extraction - take last part before state/country
    location_parts = address.split(",")
    location = location_parts[1].strip() if len(location_parts) > 1 else address
    
    # Calculate insurance coverage percentage
    total_claims = hospital_data.get("totalNumberOfClaims", 0)
    approved_claims = hospital_data.get("totalNumberOfClaimsApproved", 0)
    insurance_coverage_percent = int((approved_claims / total_claims * 100)) if total_claims > 0 else 0
    
    # Extract doctor IDs from LLM response
    top_doctor_ids = [d["doctorId"] for d in hospital_llm.get("doctors", [])]
    
    # Create a mapping of doctorId -> AI review
    doctor_ai_reviews = {d["doctorId"]: d.get("doctorAIReview", "") for d in hospital_llm.get("doctors", [])}
    
    # Format reviews for UI
    formatted_reviews = []
    for review in reviews[:2]:  # Only first 2 reviews
        try:
            payment = review.get("payment") or {}
            claim = review.get("claim") or {}
            
            formatted_review = {
                "id": review.get("reviewId", ""),
                "patientName": review.get("customerName", "Anonymous"),
                "rating": review.get("overallRating", 4),
                "date": review.get("createdAt", "")[:10] if review.get("createdAt") else "",  # Extract date part
                "treatment": review.get("procedureType", "General Treatment"),
                "cost": clean_currency_value(payment.get("totalBillAmount")),
                "insuranceCovered": clean_currency_value(claim.get("claimAmountApproved")),
                "comment": review.get("hospitalReview", ""),
                "verified": review.get("verified", False)
            }
            formatted_reviews.append(formatted_review)
        except Exception as e:
            logger.warning("Failed to format review | ReviewId=%s | Error=%s", review.get("reviewId"), str(e))
            continue
    
    return {
        "id": hospital_id,
        "name": hospital_data.get("hospitalName", ""),
        "location": location,
        "rating": hospital_data.get("rating", 0),
        "reviewCount": len(reviews),
        "imageUrl": "/default-hospital.jpg",
        "description": hospital_data.get("description", ""),
        "specialties": services[:6],  # First 6 services as specialties
        "avgCostRange": {
            "min": hospital_data.get("minCost", 0),
            "max": hospital_data.get("maxCost", 0)
        },
        "insuranceCoveragePercent": insurance_coverage_percent,
        "trustScore": 85,  # Default
        "verificationBadge": "gold",  # Default
        "aiRecommendation": hospital_llm.get("hospitalAIReview", ""),
        "reviews": formatted_reviews,  # Formatted reviews for UI
        "doctors": [],  # Empty - will be lazy loaded
        "topDoctorIds": top_doctor_ids,  # For lazy loading
        "doctorAIReviews": doctor_ai_reviews,  # AI reviews for each doctor
        "acceptedInsurance": ["Blue Cross", "United Health", "Aetna", "Medicare"]  # Default
    }


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
        query_params: Dict of query parameters (hospitalId, doctorId, limit, etc.)
    
    Returns:
        list: Review items
    """
    # Make a copy to avoid modifying the original dict
    params = query_params.copy()
    
    # Extract limit if provided, default to 100
    limit = params.pop("limit", 100)
    
    params_str = "&".join([f"{k}={v}" for k, v in params.items()])
    url = f"{API_GATEWAY_BASE_URL}/reviews?{params_str}&limit={limit}"
    
    logger.info("Fetching reviews | URL=%s | Params=%s | Limit=%d", url, params, limit)
    
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        items = data.get("items", [])
        logger.info("Reviews fetched successfully | Count=%d | Params=%s", len(items), params)
        
        return items
    
    except requests.exceptions.HTTPError as e:
        logger.error("HTTP error fetching reviews | Status=%d | URL=%s | Error=%s", 
                    e.response.status_code, url, str(e))
        return []  # Return empty list on error, don't fail the whole search
    
    except Exception as e:
        logger.error("Failed to fetch reviews | URL=%s | Params=%s | Error=%s", url, params, str(e))
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


def search_hospitals(event: dict) -> dict:
    """
    Initiate async search and return searchId immediately.
    
    Process:
    1. Parse request and validate
    2. Generate searchId
    3. Save initial status as "processing"
    4. Invoke Lambda asynchronously to process search
    5. Return searchId immediately
    
    Args:
        event: API Gateway event
    
    Returns:
        dict: API Gateway response with searchId and status
    """
    request_id = event.get("requestContext", {}).get("requestId", uuid.uuid4().hex[:12])
    logger.info("=" * 80)
    logger.info("SEARCH REQUEST START | RequestId=%s", request_id)
    logger.info("=" * 80)
    
    try:
        # Parse request body
        body = _parse_body(event)
        query = body.get("query", "").strip()
        customer_id = body.get("customerId", "").strip()
        user_context = body.get("userContext", {})
        insurance_id = user_context.get("insuranceId")
        
        logger.info(
            "Request parsed | Query='%s' | CustomerId=%s | InsuranceId=%s",
            query[:100],
            customer_id or "None",
            insurance_id or "None"
        )
        
        # Validate required fields
        if not query:
            logger.warning("Missing required field: query")
            return _error(400, "Missing required field: query")
        
        # Generate searchId
        search_id = f"search_{int(time.time())}_{request_id}"
        logger.info("Generated searchId | SearchId=%s", search_id)
        
        # Save initial status
        save_search_results(search_id, "processing")
        
        # Invoke Lambda asynchronously to process search
        function_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        
        async_payload = {
            "asyncSearch": True,
            "searchId": search_id,
            "query": query,
            "customerId": customer_id,
            "insuranceId": insurance_id
        }
        
        try:
            lambda_client.invoke(
                FunctionName=function_name,
                InvocationType="Event",  # Async invocation
                Payload=json.dumps(async_payload)
            )
            logger.info("Async Lambda invoked | SearchId=%s", search_id)
        except Exception as e:
            logger.error("Failed to invoke async Lambda | SearchId=%s | Error=%s", search_id, str(e))
            save_search_results(search_id, "error", error="Failed to start async processing")
            return _error(500, "Failed to initiate search processing")
        
        # Return immediately with searchId
        response_body = {
            "searchId": search_id,
            "status": "processing"
        }
        
        logger.info("Search initiated | SearchId=%s", search_id)
        return _ok(response_body, 202)  # 202 Accepted
    
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return _error(400, "Invalid JSON in request body")
    
    except Exception as e:
        logger.exception("Failed to initiate search | RequestId=%s", request_id)
        return _error(
            500,
            "Failed to initiate search. Please try again.",
            {"code": "INTERNAL_ERROR"}
        )


def get_search_status(event: dict) -> dict:
    """
    Get search status and results.
    Enriches hospital data on-the-fly from LLM response.
    
    Args:
        event: API Gateway event with searchId in path parameters
    
    Returns:
        dict: API Gateway response with status and enriched results (if complete)
    """
    try:
        # Extract searchId from path parameters
        path_params = event.get("pathParameters", {})
        search_id = path_params.get("searchId")
        
        if not search_id:
            logger.warning("Missing searchId in path parameters")
            return _error(400, "Missing searchId")
        
        logger.info("Getting search status | SearchId=%s", search_id)
        
        # Get results from DynamoDB
        item = get_search_results(search_id)
        
        if not item:
            logger.warning("Search not found | SearchId=%s", search_id)
            return _error(404, "Search not found", {
                "code": "SEARCH_NOT_FOUND",
                "suggestion": "The search may have expired or the searchId is invalid"
            })
        
        status = item.get("status")
        
        # If processing, return minimal response
        if status == "processing":
            return _ok({
                "searchId": search_id,
                "status": "processing"
            })
        
        # If error, return error details
        if status == "error":
            error_msg = item.get("error", "Search processing failed")
            return _error(500, error_msg, {
                "code": "SEARCH_ERROR",
                "searchId": search_id
            })
        
        # If complete, enrich and return results
        if status == "complete":
            llm_response = item.get("llmResponse", {})
            
            if not llm_response:
                logger.error("LLM response missing | SearchId=%s", search_id)
                return _error(500, "Search results corrupted")
            
            # Extract hospital IDs from LLM response
            hospitals_llm = llm_response.get("hospitals", [])
            hospital_ids = list(set([h["hospitalId"] for h in hospitals_llm]))
            
            logger.info("Enriching hospitals on-the-fly | SearchId=%s | Count=%d", search_id, len(hospital_ids))
            
            # Fetch hospital data and reviews in parallel
            hospitals_data = {}
            hospital_reviews = {}
            
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {}
                
                for hospital_id in hospital_ids:
                    future = executor.submit(fetch_from_api, "hospitals", "Hospital", hospital_id)
                    futures[future] = ("hospital", hospital_id)
                
                for hospital_id in hospital_ids:
                    future = executor.submit(fetch_reviews, {"hospitalId": hospital_id, "limit": 2})
                    futures[future] = ("hospital_reviews", hospital_id)
                
                for future in as_completed(futures):
                    task_type, resource_id = futures[future]
                    
                    try:
                        result = future.result()
                        
                        if task_type == "hospital":
                            hospitals_data[resource_id] = result
                        elif task_type == "hospital_reviews":
                            hospital_reviews[resource_id] = result
                    
                    except Exception as e:
                        logger.error(
                            "Task failed | SearchId=%s | Type=%s | ResourceId=%s | Error=%s",
                            search_id,
                            task_type,
                            resource_id,
                            str(e)
                        )
            
            # Build enriched hospitals
            enriched_hospitals = []
            
            for hospital_llm in hospitals_llm:
                hospital_id = hospital_llm["hospitalId"]
                hospital_data = hospitals_data.get(hospital_id)
                
                if not hospital_data:
                    logger.warning("Hospital data not found | SearchId=%s | HospitalId=%s", search_id, hospital_id)
                    continue
                
                reviews = hospital_reviews.get(hospital_id, [])
                
                enriched_hospital = build_enriched_hospital(
                    hospital_llm,
                    hospital_data,
                    reviews,
                    None  # insurance_id not available here
                )
                
                enriched_hospitals.append(enriched_hospital)
            
            logger.info("Hospitals enriched | SearchId=%s | Count=%d", search_id, len(enriched_hospitals))
            
            return _ok({
                "searchId": search_id,
                "status": "complete",
                "results": {
                    "aiSummary": llm_response.get("aiSummary", ""),
                    "hospitals": enriched_hospitals
                }
            })
        
        # Unknown status
        logger.error("Unknown search status | SearchId=%s | Status=%s", search_id, status)
        return _error(500, "Unknown search status")
    
    except Exception as e:
        logger.exception("Failed to get search status")
        return _error(500, "Failed to get search status")


def get_hospital_doctors(event: dict) -> dict:
    """
    Get doctors for a specific hospital (lazy loading).
    
    Args:
        event: API Gateway event with hospitalId and searchId in query parameters
    
    Returns:
        dict: API Gateway response with enriched doctor list
    """
    try:
        # Extract parameters
        query_params = event.get("queryStringParameters", {}) or {}
        hospital_id = event.get("pathParameters", {}).get("hospitalId")
        search_id = query_params.get("searchId")
        
        if not hospital_id:
            return _error(400, "Missing hospitalId")
        
        if not search_id:
            return _error(400, "Missing searchId")
        
        logger.info("Getting hospital doctors | HospitalId=%s | SearchId=%s", hospital_id, search_id)
        
        # Get search results from DynamoDB
        item = get_search_results(search_id)
        
        if not item or item.get("status") != "complete":
            return _error(404, "Search not found or not complete")
        
        # Get LLM response
        llm_response = item.get("llmResponse", {})
        
        if not llm_response:
            logger.error("LLM response missing | SearchId=%s", search_id)
            return _error(500, "Search results corrupted")
        
        # Find the hospital in LLM response
        hospitals_llm = llm_response.get("hospitals", [])
        hospital_llm = None
        
        for h in hospitals_llm:
            if h.get("hospitalId") == hospital_id:
                hospital_llm = h
                break
        
        if not hospital_llm:
            return _error(404, "Hospital not found in search results")
        
        # Get doctor IDs and AI reviews from LLM response
        doctors_llm = hospital_llm.get("doctors", [])
        doctor_ids = [d["doctorId"] for d in doctors_llm]
        doctor_ai_reviews = {d["doctorId"]: d.get("doctorAIReview", "") for d in doctors_llm}
        
        if not doctor_ids:
            logger.info("No doctors found for hospital | HospitalId=%s", hospital_id)
            return _ok({"doctors": []})
        
        logger.info("Fetching doctors | HospitalId=%s | DoctorCount=%d", hospital_id, len(doctor_ids))
        
        # Fetch doctor data and reviews in parallel
        doctors_data = {}
        doctor_reviews = {}
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {}
            
            for doctor_id in doctor_ids:
                future = executor.submit(fetch_from_api, "doctors", "Doctor", doctor_id)
                futures[future] = ("doctor", doctor_id)
            
            for doctor_id in doctor_ids:
                future = executor.submit(fetch_reviews, {"doctorId": doctor_id, "limit": 1})
                futures[future] = ("doctor_reviews", doctor_id)
            
            for future in as_completed(futures):
                task_type, resource_id = futures[future]
                
                try:
                    result = future.result()
                    
                    if task_type == "doctor":
                        doctors_data[resource_id] = result
                    elif task_type == "doctor_reviews":
                        doctor_reviews[resource_id] = result
                
                except Exception as e:
                    logger.error(
                        "Task failed | Type=%s | ResourceId=%s | Error=%s",
                        task_type,
                        resource_id,
                        str(e)
                    )
        
        # Build enriched doctor list
        enriched_doctors = []
        
        for doctor_id in doctor_ids:
            doctor_data = doctors_data.get(doctor_id)
            
            if not doctor_data:
                logger.warning("Doctor data not found | DoctorId=%s", doctor_id)
                continue
            
            reviews = doctor_reviews.get(doctor_id, [])
            
            # Parse qualifications if it's a JSON string
            qualifications = doctor_data.get("qualifications", [])
            if isinstance(qualifications, str):
                try:
                    qualifications = json.loads(qualifications)
                except:
                    qualifications = []
            
            # Build enriched doctor object with AI review from LLM response
            enriched_doctor = {
                "id": doctor_id,
                "name": doctor_data.get("doctorName", ""),
                "specialty": doctor_data.get("specialty", "General"),
                "experience": doctor_data.get("yearsOfExperience", 10),
                "qualifications": qualifications,
                "rating": doctor_data.get("rating", 4.0),
                "reviewCount": len(reviews),  # Calculate from fetched reviews
                "imageUrl": "/default-doctor.jpg",
                "aiSummary": doctor_ai_reviews.get(doctor_id, ""),  # Get AI review from LLM response
                "reviews": reviews[:1]  # First review
            }
            
            enriched_doctors.append(enriched_doctor)
        
        logger.info("Doctors fetched | HospitalId=%s | Count=%d", hospital_id, len(enriched_doctors))
        
        return _ok({"doctors": enriched_doctors})
    
    except Exception as e:
        logger.exception("Failed to get hospital doctors")
        return _error(500, "Failed to get hospital doctors")


# ---------------------------------------------------------------------------
# Lambda Handler
# ---------------------------------------------------------------------------

def lambda_handler(event: dict, context: Any) -> dict:
    """
    Main Lambda entry point for API Gateway integration.
    
    Routes:
      POST /search                                    → search_hospitals (initiate async search)
      GET  /search/{searchId}                         → get_search_status (poll for results)
      GET  /hospitals/{hospitalId}/doctors            → get_hospital_doctors (lazy load doctors)
      
    Async Processing:
      asyncSearch=True in event                       → process_search_async (background processing)
    
    Args:
        event: API Gateway event or async processing event
        context: Lambda context
    
    Returns:
        dict: API Gateway response or None for async processing
    """
    # Check if this is an async search processing invocation
    if event.get("asyncSearch"):
        search_id = event.get("searchId")
        query = event.get("query")
        customer_id = event.get("customerId")
        insurance_id = event.get("insuranceId")
        
        logger.info("Async search processing invocation | SearchId=%s", search_id)
        process_search_async(search_id, query, customer_id, insurance_id)
        return None  # No response needed for async invocation
    
    # Regular API Gateway routing
    method = (
        event.get("httpMethod") 
        or event.get("requestContext", {}).get("http", {}).get("method", "")
    ).upper()
    
    path = (
        event.get("path", "")
        or event.get("requestContext", {}).get("http", {}).get("path", "")
    ).rstrip("/").lower()
    
    logger.info("Lambda invoked | Method=%s | Path=%s", method, path)
    
    # Route: POST /search - Initiate async search
    if method == "POST" and path.endswith("/search"):
        return search_hospitals(event)
    
    # Route: GET /search/{searchId} - Get search status/results
    if method == "GET" and "/search/" in path and not path.endswith("/search"):
        return get_search_status(event)
    
    # Route: GET /hospitals/{hospitalId}/doctors - Get hospital doctors
    if method == "GET" and "/hospitals/" in path and path.endswith("/doctors"):
        return get_hospital_doctors(event)
    
    # Method not allowed
    logger.warning("Method not allowed | Method=%s | Path=%s", method, path)
    return _error(405, f"Method '{method}' not allowed on path '{path}'")
