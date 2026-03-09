# AppSync Resolvers

This directory contains JavaScript resolvers for the AppSync GraphQL API.

## Resolver Files

### Mutation.initiateSearch.js
- **Type**: Lambda resolver
- **Data Source**: InvokerLambda function
- **Purpose**: Initiates a new hospital search by invoking the InvokerLambda
- **Input**: 
  - `query: String!` - Search query
  - `customerId: String` - Customer ID (optional)
  - `userLocation: LocationInput` - User location (optional)
- **Output**: `SearchInitiated` - Contains searchId and status

### Mutation.publishAgentChunk.js
- **Type**: NONE resolver (local)
- **Data Source**: NONE
- **Purpose**: Publishes agent activity chunks to subscriptions
- **Input**:
  - `searchId: ID!` - Search identifier
  - `chunk: String!` - Activity chunk text
- **Output**: `AgentChunk` - Contains searchId, chunk, and timestamp
- **Note**: This resolver is called by WorkerLambda via HTTP POST to AppSync endpoint

### Query.getSearchResults.js
- **Type**: DynamoDB resolver
- **Data Source**: SearchResults DynamoDB table
- **Purpose**: Fetches final search results from DynamoDB
- **Input**:
  - `searchId: ID!` - Search identifier
- **Output**: `SearchResults` - Contains searchId, status, results, and error

### Subscription: onAgentActivity
- **Type**: No resolver needed!
- **Data Source**: N/A (built-in subscription)
- **Purpose**: Automatically filters and delivers events to subscribers
- **How it works**: The `@aws_subscribe(mutations: ["publishAgentChunk"])` directive in the schema tells AppSync to automatically push data from `publishAgentChunk` to subscribers
- **Filtering**: AppSync automatically filters by `searchId` argument - subscribers only receive chunks matching their searchId
- **Note**: Do NOT create a resolver file for this - AppSync handles everything automatically

## Resolver Configuration

### Data Sources

1. **InvokerLambda** (for initiateSearch)
   - Type: AWS Lambda
   - Function: searchInvokerFunction
   - IAM Role: AppSyncLambdaRole

2. **NONE** (for publishAgentChunk)
   - Type: NONE
   - Purpose: Local resolver that just publishes to subscriptions

3. **SearchResultsTable** (for getSearchResults)
   - Type: Amazon DynamoDB
   - Table: SearchResults
   - IAM Role: AppSyncDynamoDBRole

4. **Subscription** (for onAgentActivity)
   - Type: N/A (built-in subscription mechanism)
   - Purpose: Automatically filters and delivers events to subscribers
   - Note: **No resolver needed** - AppSync handles filtering automatically via `@aws_subscribe` directive

## Deployment

### Using AWS Console

1. Go to AWS AppSync Console
2. Select your API
3. Go to "Schema" section
4. For each resolver:
   - Click "Attach" next to the field
   - Select the data source
   - Choose "Unit resolver"
   - Paste the resolver code
   - Click "Save"

### Using AWS CLI

```bash
# Create data sources
aws appsync create-data-source \
  --api-id <API_ID> \
  --name InvokerLambda \
  --type AWS_LAMBDA \
  --lambda-config lambdaFunctionArn=<INVOKER_LAMBDA_ARN> \
  --service-role-arn <APPSYNC_LAMBDA_ROLE_ARN>

aws appsync create-data-source \
  --api-id <API_ID> \
  --name SearchResultsTable \
  --type AMAZON_DYNAMODB \
  --dynamodb-config tableName=SearchResults,awsRegion=eu-north-1 \
  --service-role-arn <APPSYNC_DYNAMODB_ROLE_ARN>

aws appsync create-data-source \
  --api-id <API_ID> \
  --name NoneDataSource \
  --type NONE

# Create resolvers
aws appsync create-resolver \
  --api-id <API_ID> \
  --type-name Mutation \
  --field-name initiateSearch \
  --data-source-name InvokerLambda \
  --code file://Mutation.initiateSearch.js

aws appsync create-resolver \
  --api-id <API_ID> \
  --type-name Mutation \
  --field-name publishAgentChunk \
  --data-source-name NoneDataSource \
  --code file://Mutation.publishAgentChunk.js

aws appsync create-resolver \
  --api-id <API_ID> \
  --type-name Query \
  --field-name getSearchResults \
  --data-source-name SearchResultsTable \
  --code file://Query.getSearchResults.js
```

## Testing Resolvers

### Test initiateSearch

```graphql
mutation TestInitiateSearch {
  initiateSearch(
    query: "best hospital for cardiac surgery"
    customerId: "test-user-123"
    userLocation: {
      latitude: 28.6139
      longitude: 77.2090
    }
  ) {
    searchId
    status
  }
}
```

### Test publishAgentChunk

```graphql
mutation TestPublishChunk {
  publishAgentChunk(
    searchId: "search_1234567890_abc123"
    chunk: "🚀 Starting search..."
  ) {
    searchId
    chunk
    timestamp
  }
}
```

### Test getSearchResults

```graphql
query TestGetResults {
  getSearchResults(searchId: "search_1234567890_abc123") {
    searchId
    status
    results {
      aiSummary
      hospitals {
        id
        name
        location
        rating
      }
    }
    error
  }
}
```

### Test Subscription

```graphql
subscription TestSubscription {
  onAgentActivity(searchId: "search_1234567890_abc123") {
    searchId
    chunk
    timestamp
  }
}
```

## Troubleshooting

### Resolver Errors

Check CloudWatch Logs:
- Log Group: `/aws/appsync/apis/<API_ID>`
- Look for resolver execution logs

### Common Issues

1. **Lambda timeout**: Increase InvokerLambda timeout
2. **DynamoDB access denied**: Check IAM role permissions
3. **Subscription not receiving data**: Verify publishAgentChunk is being called
4. **Invalid response format**: Check Lambda return value matches GraphQL schema

## IAM Permissions

### AppSyncLambdaRole

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:*:*:function:searchInvokerFunction"
    }
  ]
}
```

### AppSyncDynamoDBRole

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:Query"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/SearchResults"
    }
  ]
}
```
