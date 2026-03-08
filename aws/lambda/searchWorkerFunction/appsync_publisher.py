"""
AppSync Publisher Module
========================
Handles publishing agent activity chunks to AWS AppSync for real-time streaming to UI.
"""

import json
import logging
import os
import urllib3
from datetime import datetime, timezone

logger = logging.getLogger()

# AppSync configuration
APPSYNC_ENDPOINT = os.environ.get("APPSYNC_ENDPOINT")
APPSYNC_API_KEY = os.environ.get("APPSYNC_API_KEY")

# HTTP connection pool for AppSync requests
http = urllib3.PoolManager(maxsize=10)


def publish_agent_chunk(search_id: str, chunk: str, max_retries: int = 3) -> bool:
    """
    Publish agent activity chunk to AppSync.
    
    Args:
        search_id: Search identifier
        chunk: Activity text to publish
        max_retries: Maximum retry attempts
    
    Returns:
        bool: True if published successfully, False otherwise
    """
    if not APPSYNC_ENDPOINT or not APPSYNC_API_KEY:
        logger.warning("AppSync not configured, skipping chunk publish")
        return False
    
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
    
    for attempt in range(1, max_retries + 1):
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
            
            if response.status == 200:
                logger.info(f"Published chunk to AppSync | SearchId={search_id} | Attempt={attempt}")
                return True
            else:
                logger.warning(
                    f"AppSync publish failed | SearchId={search_id} | Status={response.status} | Attempt={attempt}"
                )
        
        except Exception as e:
            logger.error(
                f"AppSync publish error | SearchId={search_id} | Attempt={attempt} | Error={str(e)}"
            )
        
        if attempt < max_retries:
            import time
            time.sleep(2 ** (attempt - 1))  # Exponential backoff: 1s, 2s, 4s
    
    logger.error(f"Failed to publish chunk after {max_retries} attempts | SearchId={search_id}")
    return False


def simplify_trace(event: dict) -> str:
    """
    Simplify Bedrock Agent trace event to human-readable text.
    
    Args:
        event: Agent event from completion stream
    
    Returns:
        str: Simplified human-readable text
    """
    try:
        if "trace" not in event:
            return "Processing..."
        
        orchestration = event["trace"]["trace"]["orchestrationTrace"]
        
        # Extract rationale (agent's reasoning)
        if "rationale" in orchestration:
            rationale_text = orchestration["rationale"]["text"]
            # Truncate if too long
            if len(rationale_text) > 200:
                rationale_text = rationale_text[:197] + "..."
            return f"💭 {rationale_text}"
        
        # Model invocation input
        if "modelInvocationInput" in orchestration:
            return "🤔 Agent thinking..."
        
        # Model invocation output
        if "modelInvocationOutput" in orchestration:
            return "✓ Model responded"
        
        # Observation (action group or knowledge base)
        if "observation" in orchestration:
            obs = orchestration["observation"]
            
            if "actionGroupInvocationOutput" in obs:
                return "🔍 Searching database..."
            
            if "knowledgeBaseLookupOutput" in obs:
                return "📚 Consulting knowledge base..."
            
            if "finalResponse" in obs:
                return "📝 Preparing final response..."
        
        return "Processing..."
    
    except Exception as e:
        logger.warning(f"Failed to simplify trace: {e}")
        return "Processing..."
