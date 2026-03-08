---
feature: appsync-streaming-search
created: 2024-03-08
status: draft
---

# AppSync Streaming Search - Requirements

## 1. Overview

Replace the current polling-based search mechanism with AWS AppSync real-time subscriptions to stream Bedrock Agent activity to the UI. This provides users with live feedback on the AI agent's thought process while searching for hospitals.

## 2. User Stories

### 2.1 Real-Time Agent Activity Streaming

**As a** user searching for hospitals  
**I want to** see the AI agent's thought process in real-time  
**So that** I understand what the system is doing and feel confident in the search process

#### Acceptance Criteria

1. WHEN I submit a search query, THE system SHALL display an "AI Agent Activity" container below the search bar
2. THE "AI Agent Activity" container SHALL show streaming updates of the agent's reasoning and actions
3. THE streaming updates SHALL include:
   - Agent rationale text (e.g., "Analyzing your requirements...")
   - Model invocation status (e.g., "Agent thinking...")
   - Processing status (e.g., "Searching hospitals...")
4. THE updates SHALL appear in real-time as the agent processes the query
5. WHEN the agent completes processing, THE system SHALL display the final hospital results
6. THE "AI Agent Activity" container SHALL remain visible alongside the loading spinner
7. THE streaming SHALL complete within 30 seconds or show an error

### 2.2 Seamless Architecture Migration

**As a** developer  
**I want to** migrate from polling to AppSync subscriptions  
**So that** the system is more efficient and provides better user experience

#### Acceptance Criteria

1. THE system SHALL use AWS AppSync for real-time communication
2. THE search flow SHALL use two Lambda functions:
   - InvokerLambda: Receives search request and triggers async processing
   - WorkerLambda: Processes search and streams updates
3. THE WorkerLambda SHALL invoke Bedrock Agent with `enableTrace=True`
4. THE WorkerLambda SHALL publish agent trace events to AppSync
5. THE WorkerLambda SHALL store final results in DynamoDB (existing behavior)
6. THE hospital detail page SHALL continue to work with stored DynamoDB results
7. THE lazy-loading doctors endpoint SHALL continue to work unchanged

### 2.3 Backward Compatibility

**As a** system administrator  
**I want to** ensure existing functionality continues to work  
**So that** the migration doesn't break dependent features

#### Acceptance Criteria

1. THE `/hospitals/{hospitalId}/doctors` endpoint SHALL continue to work
2. THE DynamoDB SearchResults table SHALL continue to store search results
3. THE hospital detail page SHALL retrieve results from DynamoDB
4. THE search results SHALL include all existing fields (coordinates, distance, etc.)
5. THE user location tracking SHALL continue to work

## 3. Functional Requirements

### 3.1 AppSync GraphQL Schema

#### 3.1.1 Types

```graphql
type AgentChunk {
  searchId: ID!
  chunk: String!
  timestamp: String!
}
```

#### 3.1.2 Mutations

```graphql
type Mutation {
  # Initiate search - triggers InvokerLambda
  initiateSearch(query: String!, customerId: String, userLocation: LocationInput): SearchInitiated
  
  # Publish agent activity chunk - called by WorkerLambda
  publishAgentChunk(searchId: ID!, chunk: String!): AgentChunk
}

input LocationInput {
  latitude: Float!
  longitude: Float!
}

type SearchInitiated {
  searchId: ID!
  status: String!
}
```

#### 3.1.3 Subscriptions

```graphql
type Subscription {
  # Subscribe to agent activity for a specific search
  onAgentActivity(searchId: ID!): AgentChunk
    @aws_subscribe(mutations: ["publishAgentChunk"])
}
```

#### 3.1.4 Queries

```graphql
type Query {
  # Get final search results from DynamoDB
  getSearchResults(searchId: ID!): SearchResults
}

type SearchResults {
  searchId: ID!
  status: String!
  results: SearchResultsData
  error: String
}

type SearchResultsData {
  aiSummary: String!
  hospitals: [Hospital!]!
}
```

### 3.2 InvokerLambda Function

#### 3.2.1 Purpose
Receives search requests from AppSync and asynchronously invokes WorkerLambda.

#### 3.2.2 Input (from AppSync mutation)
```json
{
  "query": "affordable cardiac surgery in Hyderabad",
  "customerId": "customer_123",
  "userLocation": {
    "latitude": 17.385044,
    "longitude": 78.486671
  }
}
```

#### 3.2.3 Behavior
1. Generate unique `searchId`
2. Save initial status "processing" to DynamoDB
3. Invoke WorkerLambda asynchronously with:
   - searchId
   - query
   - customerId
   - userLocation
4. Return immediately with searchId

#### 3.2.4 Output
```json
{
  "searchId": "search_1234567890_abc123",
  "status": "processing"
}
```

### 3.3 WorkerLambda Function

#### 3.3.1 Purpose
Processes search by invoking Bedrock Agent and streams activity to AppSync.

#### 3.3.2 Input (from InvokerLambda)
```json
{
  "searchId": "search_1234567890_abc123",
  "query": "affordable cardiac surgery in Hyderabad",
  "customerId": "customer_123",
  "userLocation": {
    "latitude": 17.385044,
    "longitude": 78.486671
  }
}
```

#### 3.3.3 Behavior
1. Invoke Bedrock Agent with `enableTrace=True`
2. Process agent event stream:
   - Extract trace events (rationale, model invocations, etc.)
   - Simplify trace to human-readable text
   - Buffer 4 events
   - Publish buffer to AppSync via `publishAgentChunk` mutation
3. When agent completes:
   - Parse final JSON response
   - Store in DynamoDB with status "complete"
   - Publish "Completed" chunk to AppSync
4. On error:
   - Store error in DynamoDB with status "error"
   - Publish error chunk to AppSync

#### 3.3.4 Trace Simplification Logic
```python
def simplify_trace(event):
    if "trace" not in event:
        return "Processing..."
    
    orchestration = event["trace"]["trace"]["orchestrationTrace"]
    
    if "rationale" in orchestration:
        return orchestration["rationale"]["text"]
    
    if "modelInvocationInput" in orchestration:
        return "Agent thinking..."
    
    if "modelInvocationOutput" in orchestration:
        return "Model responded"
    
    return "Processing..."
```

#### 3.3.5 AppSync Publishing
```python
def publish_chunk(search_id, chunk):
    mutation = """
    mutation PublishAgentChunk($searchId: ID!, $chunk: String!) {
        publishAgentChunk(searchId: $searchId, chunk: $chunk) {
            searchId
            chunk
            timestamp
        }
    }
    """
    
    # Use urllib3 or requests to POST to AppSync endpoint
    # Include x-api-key header for authentication
```

### 3.4 UI Changes

#### 3.4.1 New Component: AgentActivityFeed

**Location**: `app/src/app/components/AgentActivityFeed.tsx`

**Props**:
```typescript
interface AgentActivityFeedProps {
  searchId: string;
  onComplete: () => void;
}
```

**Behavior**:
1. Subscribe to `onAgentActivity(searchId)` when mounted
2. Display chunks in a scrollable container
3. Auto-scroll to latest chunk
4. Show timestamp for each chunk
5. Call `onComplete()` when "Completed" chunk received
6. Handle errors gracefully

#### 3.4.2 Modified Component: Home.tsx

**Changes**:
1. Replace `searchHospitalsAPI()` with AppSync mutation `initiateSearch()`
2. Show `AgentActivityFeed` component when search starts
3. Keep loading spinner visible alongside activity feed
4. When activity feed completes, fetch final results from DynamoDB
5. Display hospital results as before

#### 3.4.3 AppSync Client Setup

**Location**: `app/src/app/services/appsync.ts`

**Setup**:
```typescript
import { AWSAppSyncClient } from 'aws-appsync';

const client = new AWSAppSyncClient({
  url: process.env.VITE_APPSYNC_ENDPOINT,
  region: 'us-east-1',
  auth: {
    type: 'API_KEY',
    apiKey: process.env.VITE_APPSYNC_API_KEY,
  },
});
```

## 4. Non-Functional Requirements

### 4.1 Performance

1. THE WorkerLambda SHALL complete Bedrock Agent invocation within 30 seconds
2. THE AppSync subscription SHALL deliver chunks with < 500ms latency
3. THE UI SHALL render new chunks within 100ms of receiving them
4. THE system SHALL handle up to 100 concurrent searches

### 4.2 Reliability

1. THE system SHALL retry failed AppSync publishes up to 3 times
2. THE system SHALL store all results in DynamoDB regardless of streaming success
3. THE UI SHALL fall back to polling if WebSocket connection fails
4. THE system SHALL handle Bedrock Agent timeouts gracefully

### 4.3 Security

1. THE AppSync API SHALL use API Key authentication
2. THE API Key SHALL be stored in environment variables
3. THE AppSync endpoint SHALL have CORS enabled for the UI domain
4. THE Lambda functions SHALL have minimal IAM permissions

### 4.4 Observability

1. THE WorkerLambda SHALL log all agent events to CloudWatch
2. THE system SHALL track streaming latency metrics
3. THE system SHALL alert on failed searches
4. THE UI SHALL log subscription connection status

## 5. Technical Constraints

### 5.1 AWS Services

1. MUST use AWS AppSync for GraphQL API
2. MUST use AWS Lambda for compute
3. MUST use DynamoDB for result storage (existing table)
4. MUST use Bedrock Agent for AI processing (existing agent)

### 5.2 Compatibility

1. MUST maintain existing DynamoDB schema
2. MUST keep `/hospitals/{hospitalId}/doctors` endpoint working
3. MUST preserve user location tracking
4. MUST maintain hospital detail page functionality

### 5.3 Migration

1. MUST refactor existing `searchFunction` Lambda into WorkerLambda
2. MUST create new InvokerLambda
3. MUST update API Gateway to route to AppSync mutation (or remove REST endpoint)
4. MUST update UI to use AppSync subscriptions

## 6. Breaking Changes

### 6.1 API Changes

**BREAKING**: The REST endpoint `POST /search` will be replaced with AppSync mutation `initiateSearch`

**Impact**:
- `app/src/app/services/api.ts` - `initiateSearch()` function
- `app/src/app/pages/Home.tsx` - `handleSearch()` function
- Any external clients calling the REST API

**Migration**:
1. Update UI to use AppSync mutation
2. Remove polling logic from `api.ts`
3. Add AppSync client setup
4. Update environment variables

### 6.2 Lambda Changes

**BREAKING**: `searchFunction` Lambda will be split into two functions

**Impact**:
- Deployment scripts: `deploy.ps1`, `deploy.sh`
- API Gateway routes
- CloudWatch log groups
- IAM roles and permissions

**Migration**:
1. Create new `searchInvokerFunction` Lambda
2. Rename `searchFunction` to `searchWorkerFunction`
3. Update deployment scripts
4. Update API Gateway integration
5. Update IAM policies

### 6.3 Environment Variables

**NEW**: AppSync configuration required in UI

**Required**:
- `VITE_APPSYNC_ENDPOINT` - AppSync GraphQL endpoint
- `VITE_APPSYNC_API_KEY` - AppSync API key

**Migration**:
1. Add to `app/.env.local`
2. Add to deployment configuration
3. Document in README

## 7. Dependencies

### 7.1 AWS Resources

1. AWS AppSync API (new)
2. AppSync API Key (new)
3. InvokerLambda function (new)
4. WorkerLambda function (refactored from searchFunction)
5. DynamoDB SearchResults table (existing)
6. Bedrock Agent (existing)

### 7.2 NPM Packages

1. `aws-appsync` - AppSync client
2. `graphql` - GraphQL queries/mutations
3. `graphql-tag` - GraphQL template literals

### 7.3 Python Packages

1. `urllib3` - HTTP client for AppSync (already in requirements.txt)
2. `boto3` - AWS SDK (already in requirements.txt)

## 8. Testing Requirements

### 8.1 Unit Tests

1. TEST InvokerLambda generates valid searchId
2. TEST InvokerLambda invokes WorkerLambda asynchronously
3. TEST WorkerLambda simplifies trace events correctly
4. TEST WorkerLambda publishes chunks to AppSync
5. TEST WorkerLambda stores results in DynamoDB

### 8.2 Integration Tests

1. TEST end-to-end search flow with real Bedrock Agent
2. TEST AppSync subscription receives all chunks
3. TEST UI displays chunks in real-time
4. TEST hospital detail page retrieves results from DynamoDB
5. TEST lazy-loading doctors endpoint still works

### 8.3 Error Scenarios

1. TEST Bedrock Agent timeout handling
2. TEST AppSync publish failure handling
3. TEST WebSocket connection failure fallback
4. TEST invalid search query handling
5. TEST DynamoDB write failure handling

## 9. Rollout Plan

### Phase 1: Infrastructure Setup
1. Create AppSync API with schema
2. Create InvokerLambda function
3. Refactor searchFunction to WorkerLambda
4. Test Lambda-to-AppSync publishing

### Phase 2: UI Integration
1. Add AppSync client to UI
2. Create AgentActivityFeed component
3. Update Home.tsx to use AppSync
4. Test subscription flow

### Phase 3: Testing & Validation
1. Run integration tests
2. Test error scenarios
3. Validate hospital detail page
4. Validate doctors lazy-loading

### Phase 4: Deployment
1. Deploy AppSync API
2. Deploy Lambda functions
3. Update UI environment variables
4. Deploy UI changes
5. Monitor CloudWatch logs

## 10. Success Criteria

1. Users see real-time agent activity during search
2. Search completes within 30 seconds
3. Hospital results display correctly
4. Hospital detail page works unchanged
5. Doctors lazy-loading works unchanged
6. No increase in error rate
7. CloudWatch logs show successful streaming
