"""
AWS Lambda – Hospital Search Worker with AppSync Streaming
===========================================================
This Lambda function processes hospital search requests with real-time streaming:
1. Invoked asynchronously by InvokerLambda
2. Invokes AWS Bedrock Agent with trace enabled
3. Streams agent activity to AppSync in real-time
4. Stores final results in DynamoDB

Environment variables (required):
  BEDROCK_AGENT_ID       – Bedrock Agent ID
  BEDROCK_AGENT_ALIAS_ID – Agent Alias ID
  BEDROCK_REGION         – AWS region for Bedrock
  API_GATEWAY_BASE_URL   – Base URL for API Gateway endpoints
  DYNAMODB_TABLE_NAME    – SearchResults table name
  DYNAMODB_REGION        – DynamoDB region
  APPSYNC_ENDPOINT       – AppSync GraphQL endpoint URL
  APPSYNC_API_KEY        – AppSync API key
"""

import json
import boto3
import logging
import time
import urllib3
import os
import re
import math
from datetime import datetime, timezone
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError

# ---------- logging ----------
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------- AWS clients ----------
bedrock_agent = boto3.client("bedrock-agent-runtime", region_name=os.environ.get("BEDROCK_REGION", "us-east-1"))
dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("DYNAMODB_REGION", "eu-north-1"))
search_results_table = dynamodb.Table(os.environ.get("DYNAMODB_TABLE_NAME", "SearchResults"))


AGENT_ID = "ASPMAO88W7"
AGENT_ALIAS_ID = "I2FYS2ELU3"

REGION = "us-east-1"
APPSYNC_API_ID = "xuwjgn5z4zgjfl474tpyoyuoza"
# ---------- constants ----------
BEDROCK_AGENT_ID = os.environ.get("BEDROCK_AGENT_ID", "ASPMAO88W7")
BEDROCK_AGENT_ALIAS_ID = os.environ.get("BEDROCK_AGENT_ALIAS_ID", "I2FYS2ELU3")
API_GATEWAY_BASE_URL = os.environ.get("API_GATEWAY_BASE_URL", "https://ri8zkgmzlb.execute-api.us-east-1.amazonaws.com")
APPSYNC_ENDPOINT = "https://xg5bjurpsbgfda2nufr6c46n7e.appsync-api.us-east-1.amazonaws.com/graphql"
APPSYNC_API_KEY = "da2-ezoxtcpclffrdkbysmv22sjiei"
SEARCH_RESULT_TTL_HOURS = 5
LLM_MAX_RETRIES = 3
MAX_WORKERS = 20
REQUEST_TIMEOUT = 10

# persistent connection pool
http = urllib3.PoolManager(maxsize=10)


# ---------- Helper Functions ----------

class DecimalEncoder(json.JSONEncoder):
    """Serialize DynamoDB Decimal values."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)


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


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points using Haversine formula."""
    try:
        R = 6371.0  # Earth's radius in kilometers
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = math.sin(delta_lat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        return round(distance, 1)
    except Exception as e:
        logger.warning(f"Failed to calculate distance: {e}")
        return None


def save_search_results(search_id: str, status: str, llm_response: dict = None, error: str = None, user_location: dict = None):
    """Save search results to DynamoDB."""
    try:
        ttl = int(time.time()) + (SEARCH_RESULT_TTL_HOURS * 3600)
        
        item = {
            "searchId": search_id,
            "status": status,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "ttl": ttl
        }
        
        if user_location:
            item["userLocation"] = convert_floats_to_decimal(user_location)
        
        if llm_response:
            item["llmResponse"] = convert_floats_to_decimal(llm_response)
        
        if error:
            item["error"] = error
        
        search_results_table.put_item(Item=item)
        logger.info(f"Search results saved | SearchId={search_id} | Status={status}")
    
    except Exception as e:
        logger.error(f"Failed to save search results | SearchId={search_id} | Error={str(e)}")
        raise


# ---------- AppSync Publishing ----------

def simplify_trace(event):
    """Simplify Bedrock Agent trace event to human-readable text."""
    try:
        if "trace" not in event:
            return None
        
        orchestration = event["trace"]["trace"]["orchestrationTrace"]
        
        if "rationale" in orchestration:
            text = orchestration["rationale"]["text"]
            # Truncate if too long
            if len(text) > 200:
                text = text[:197] + "..."
            return f"💭 {text}"
        
        if "modelInvocationInput" in orchestration:
            return "🤔 Agent thinking..."
        
        if "modelInvocationOutput" in orchestration:
            return "✓ Model responded"
        
        if "observation" in orchestration:
            obs = orchestration["observation"]
            if "actionGroupInvocationOutput" in obs:
                return "🔍 Searching database..."
            if "knowledgeBaseLookupOutput" in obs:
                return "📚 Consulting knowledge base..."
        
        return None
    
    except Exception as e:
        logger.warning(f"Failed to simplify trace: {e}")
        return None


def publish_chunk(search_id, chunk):
    """Publish agent activity chunk to AppSync."""
    if not APPSYNC_ENDPOINT or not APPSYNC_API_KEY:
        logger.warning("AppSync not configured, skipping chunk publish")
        return
    
    mutation = """
    mutation PublishAgentChunk($searchId: ID!, $chunk: String!) {
        publishAgentChunk(searchId: $searchId, chunk: $chunk) {
            searchId
            chunk
            timestamp
        }
    }
    """
    
    body = json.dumps({
        "query": mutation,
        "variables": {
            "searchId": search_id,
            "chunk": chunk
        }
    })
    
    try:
        response = http.request(
            "POST",
            APPSYNC_ENDPOINT,
            body=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": APPSYNC_API_KEY
            },
            timeout=5.0
        )
        
        logger.info(f"AppSync response | SearchId={search_id} | Status={response.status}")
    
    except Exception as e:
        logger.error(f"AppSync publish error | SearchId={search_id} | Error={str(e)}")


# ---------- Bedrock Agent Integration ----------

def invoke_bedrock_agent_with_streaming(search_id: str, query: str, customer_id: str, max_retries: int = LLM_MAX_RETRIES) -> dict:
    """
    Invoke Bedrock Agent with trace streaming to AppSync.
    """
    session_id = "1448d478-2001-7004-684a-512247f811da"
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Invoking Bedrock Agent | Attempt={attempt}/{max_retries} | SearchId={search_id} | Query='{query[:100]}'")
            
            response = bedrock_agent.invoke_agent(
                agentId=BEDROCK_AGENT_ID,
                agentAliasId=BEDROCK_AGENT_ALIAS_ID,
                sessionId=session_id,
                inputText=query,
                enableTrace=True  # CRITICAL: Enable trace for streaming
            )
            
            full_response = ""
            buffer = []
            chunk_count = 0
            trace_count = 0
            
            # Process streaming events
            for event in response.get("completion", []):
                chunk_count += 1
                
                # Collect response chunks
                if "chunk" in event:
                    chunk = event["chunk"]
                    if "bytes" in chunk:
                        chunk_data = chunk["bytes"].decode("utf-8")
                        full_response += chunk_data
                
                # Simplify trace and add to buffer
                simplified = simplify_trace(event)
                if simplified:
                    trace_count += 1
                    logger.info(f"Trace {trace_count}: {simplified}")
                    buffer.append(simplified)
                    
                    # Publish every 4 events
                    if len(buffer) >= 4:
                        publish_chunk(search_id, "\n".join(buffer))
                        buffer = []
                        time.sleep(0.2)  # Rate limiting
            
            # Publish remaining buffer
            if buffer:
                publish_chunk(search_id, "\n".join(buffer))
            
            # Ensure we received some response
            if not full_response:
                logger.error(f"No response received from Bedrock Agent | ChunkCount={chunk_count}")
                raise Exception("Empty response from Bedrock Agent")
            
            logger.info(f"Bedrock Agent response received | Chunks={chunk_count} | Traces={trace_count} | ResponseLength={len(full_response)}")
            
            # Parse JSON response
            json_start = full_response.find('{')
            if json_start == -1:
                logger.error(f"No JSON object found in response | Response={full_response[:500]}")
                raise ValueError("No JSON object found in Bedrock Agent response")
            
            json_str = full_response[json_start:]
            
            # Clean JSON
            json_str_stripped = json_str.strip()
            if not json_str_stripped.endswith('}'):
                last_brace = json_str_stripped.rfind('}')
                if last_brace > 0:
                    json_str = json_str_stripped[:last_brace + 1]
            
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
            json_str = re.sub(r',\s*,', ',', json_str)
            
            llm_data = json.loads(json_str)
            logger.info(f"LLM response parsed | Hospitals={len(llm_data.get('hospitals', []))} | HasSummary={'aiSummary' in llm_data}")
            
            return llm_data
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response | Attempt={attempt} | Error={str(e)}")
            if attempt < max_retries:
                time.sleep(1)
                continue
            raise ValueError(f"Invalid JSON response after {max_retries} attempts: {str(e)}")
        
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_msg = e.response["Error"]["Message"]
            logger.error(f"Bedrock Agent invocation failed | Attempt={attempt} | ErrorCode={error_code}")
            if attempt < max_retries:
                time.sleep(1)
                continue
            raise Exception(f"Bedrock Agent error after {max_retries} attempts: {error_code} - {error_msg}")
        
        except Exception as e:
            logger.error(f"Unexpected error invoking Bedrock Agent | Attempt={attempt} | Error={str(e)}")
            if attempt < max_retries:
                time.sleep(1)
                continue
            raise


# ---------- Data Enrichment ----------

def fetch_from_api(endpoint: str, resource_type: str, resource_id: str = None) -> dict:
    """Fetch data from API Gateway endpoint."""
    if resource_id:
        url = f"{API_GATEWAY_BASE_URL}/{endpoint}/{resource_id}"
    else:
        url = f"{API_GATEWAY_BASE_URL}/{endpoint}"
    
    try:
        response = http.request("GET", url, timeout=REQUEST_TIMEOUT)
        
        if response.status != 200:
            raise Exception(f"HTTP {response.status}")
        
        return json.loads(response.data.decode('utf-8'))
    except Exception as e:
        logger.error(f"API request failed | Type={resource_type} | URL={url} | Error={str(e)}")
        raise


def fetch_reviews(query_params: dict) -> list:
    """Fetch reviews with query parameters."""
    params = query_params.copy()
    limit = params.pop("limit", 100)
    
    params_str = "&".join([f"{k}={v}" for k, v in params.items()])
    url = f"{API_GATEWAY_BASE_URL}/reviews?{params_str}&limit={limit}"
    
    try:
        response = http.request("GET", url, timeout=REQUEST_TIMEOUT)
        
        if response.status != 200:
            logger.error(f"Failed to fetch reviews | URL={url} | Status={response.status}")
            return []
        
        data = json.loads(response.data.decode('utf-8'))
        return data.get("items", [])
    except Exception as e:
        logger.error(f"Failed to fetch reviews | URL={url} | Error={str(e)}")
        return []


def build_enriched_hospital(hospital_llm: dict, hospital_data: dict, reviews: list, user_location: dict = None) -> dict:
    """Build enriched hospital object for UI."""
    
    def clean_currency_value(value) -> int:
        if value is None:
            return 0
        value_str = str(value)
        cleaned = value_str.replace("₹", "").replace("$", "").replace(",", "").strip()
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
    
    # Extract location
    address = hospital_data.get("address", "")
    location_parts = address.split(",")
    location = location_parts[1].strip() if len(location_parts) > 1 else address
    
    # Insurance coverage
    insurance_coverage_raw = hospital_data.get("insuranceCoverage", 0)
    insurance_coverage_percent = int(float(insurance_coverage_raw) * 100) if insurance_coverage_raw else 0
    
    # Doctor IDs and AI reviews
    top_doctor_ids = [d["doctorId"] for d in hospital_llm.get("doctors", [])]
    doctor_ai_reviews = {d["doctorId"]: d.get("doctorAIReview", "") for d in hospital_llm.get("doctors", [])}
    
    # Format reviews
    formatted_reviews = []
    for review in reviews[:5]:
        try:
            payment = review.get("payment") or {}
            claim = review.get("claim") or {}
            
            rating = review.get("overallRating")
            if rating is not None:
                try:
                    rating = int(rating)
                except (ValueError, TypeError):
                    rating = None
            
            formatted_review = {
                "id": review.get("reviewId", ""),
                "patientName": review.get("customerName", ""),
                "rating": rating,
                "date": review.get("createdAt", "")[:10] if review.get("createdAt") else "",
                "treatment": review.get("procedureType", "General Treatment"),
                "cost": clean_currency_value(payment.get("totalBillAmount")),
                "insuranceCovered": clean_currency_value(claim.get("claimAmountApproved")),
                "comment": review.get("hospitalReview", ""),
                "verified": review.get("verified", False)
            }
            formatted_reviews.append(formatted_review)
        except Exception as e:
            logger.warning(f"Failed to format review | ReviewId={review.get('reviewId')} | Error={str(e)}")
            continue
    
    # Parse hospital coordinates
    hospital_lat, hospital_lon = None, None
    distance_km = None
    
    hospital_location_str = hospital_data.get("location", "")
    if hospital_location_str:
        try:
            parts = hospital_location_str.split(",")
            if len(parts) == 2:
                hospital_lat = float(parts[0].strip())
                hospital_lon = float(parts[1].strip())
        except Exception as e:
            logger.warning(f"Failed to parse hospital location | HospitalId={hospital_id} | Error={str(e)}")
    
    # Calculate distance
    if hospital_lat and hospital_lon and user_location:
        if "latitude" in user_location and "longitude" in user_location:
            user_lat = float(user_location["latitude"]) if isinstance(user_location["latitude"], Decimal) else user_location["latitude"]
            user_lon = float(user_location["longitude"]) if isinstance(user_location["longitude"], Decimal) else user_location["longitude"]
            distance_km = calculate_distance(user_lat, user_lon, hospital_lat, hospital_lon)
    
    return {
        "id": hospital_id,
        "name": hospital_data.get("hospitalName", ""),
        "location": location,
        "coordinates": {
            "latitude": hospital_lat,
            "longitude": hospital_lon
        } if hospital_lat and hospital_lon else None,
        "distance": distance_km,
        "rating": hospital_data.get("rating", 0),
        "reviewCount": len(reviews),
        "imageUrl": "/default-hospital.jpg",
        "description": hospital_data.get("description", ""),
        "specialties": services[:6],
        "avgCostRange": {
            "min": hospital_data.get("minCost", 0),
            "max": hospital_data.get("maxCost", 0)
        },
        "insuranceCoveragePercent": insurance_coverage_percent,
        "trustScore": 85,
        "verificationBadge": "gold",
        "aiRecommendation": hospital_llm.get("hospitalAIReview", ""),
        "reviews": formatted_reviews,
        "doctors": [],
        "topDoctorIds": top_doctor_ids,
        "doctorAIReviews": doctor_ai_reviews,
        "acceptedInsurance": ["Blue Cross", "United Health", "Aetna", "Medicare"]
    }


# ---------- Lambda Handler ----------

def lambda_handler(event, context):
    """
    Main handler for WorkerLambda.
    Invoked asynchronously by InvokerLambda.
    """
    try:
        logger.info(f"Worker Lambda started | Event: {json.dumps(event)}")
        
        search_id = event.get("searchId")
        query = event.get("query")
        customer_id = event.get("customerId", "anonymous")
        user_location = event.get("userLocation")
        
        # Publish initial status
        publish_chunk(search_id, "🚀 Starting AI-powered hospital search...")
        
        # Invoke Bedrock Agent with streaming
        llm_response = invoke_bedrock_agent_with_streaming(search_id, query, customer_id)
        
        # Validate response
        if not llm_response.get("hospitals"):
            logger.warning(f"LLM returned no hospitals | SearchId={search_id}")
            save_search_results(search_id, "complete", llm_response=llm_response, user_location=user_location)
            publish_chunk(search_id, "⚠️ No hospitals found matching your criteria")
            return {
                "statusCode": 200,
                "body": json.dumps({"searchId": search_id, "hospitals": 0})
            }
        
        hospital_count = len(llm_response.get("hospitals", []))
        logger.info(f"LLM response validated | SearchId={search_id} | HospitalCount={hospital_count}")
        
        # Publish enrichment status
        publish_chunk(search_id, f"📊 Enriching data for {hospital_count} hospitals...")
        
        # Extract hospital IDs
        hospitals_llm = llm_response.get("hospitals", [])
        hospital_ids = list(set([h["hospitalId"] for h in hospitals_llm]))
        
        # Fetch hospital data and reviews in parallel
        hospitals_data = {}
        hospital_reviews = {}
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {}
            
            for hospital_id in hospital_ids:
                future = executor.submit(fetch_from_api, "hospitals", "Hospital", hospital_id)
                futures[future] = ("hospital", hospital_id)
            
            for hospital_id in hospital_ids:
                future = executor.submit(fetch_reviews, {"hospitalId": hospital_id, "limit": 5})
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
                    logger.error(f"Task failed | Type={task_type} | ResourceId={resource_id} | Error={str(e)}")
        
        # Build enriched hospitals
        enriched_hospitals = []
        for hospital_llm in hospitals_llm:
            hospital_id = hospital_llm["hospitalId"]
            hospital_data = hospitals_data.get(hospital_id)
            
            if not hospital_data:
                logger.warning(f"Hospital data not found | HospitalId={hospital_id}")
                continue
            
            reviews = hospital_reviews.get(hospital_id, [])
            enriched_hospital = build_enriched_hospital(hospital_llm, hospital_data, reviews, user_location)
            enriched_hospitals.append(enriched_hospital)
        
        # Update LLM response with enriched hospitals
        llm_response["hospitals"] = enriched_hospitals
        
        # Store results in DynamoDB
        logger.info(f"Storing results | SearchId={search_id} | Hospitals={len(enriched_hospitals)}")
        save_search_results(search_id, "complete", llm_response=llm_response, user_location=user_location)
        
        # Publish completion
        publish_chunk(search_id, f"✅ Search completed! Found {len(enriched_hospitals)} hospitals.")
        
        logger.info(f"Worker completed successfully | SearchId={search_id}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "searchId": search_id,
                "status": "complete",
                "hospitals": len(enriched_hospitals)
            })
        }
    
    except Exception as e:
        logger.exception(f"Worker failed | SearchId={search_id if 'search_id' in locals() else 'unknown'}")
        
        # Store error in DynamoDB
        if 'search_id' in locals():
            save_search_results(search_id, "error", error=str(e), user_location=user_location if 'user_location' in locals() else None)
            
            # Publish error
            try:
                publish_chunk(search_id, f"❌ Error: {str(e)}")
            except:
                pass
        
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
