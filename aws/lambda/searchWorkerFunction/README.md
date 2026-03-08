# Search Worker Lambda Function

## Overview

This Lambda function processes hospital search requests with real-time streaming to AppSync. It is invoked asynchronously by the InvokerLambda and streams agent activity to the UI via AppSync subscriptions.

## Architecture

```
InvokerLambda → WorkerLambda (async)
                    ↓
              Bedrock Agent (with trace)
                    ↓
              AppSync (streaming)
                    ↓
              DynamoDB (final results)
```

## Features

- ✅ Real-time agent activity streaming via AppSync
- ✅ Bedrock Agent invocation with trace enabled
- ✅ Parallel data enrichment from API Gateway
- ✅ Distance calculation based on user location
- ✅ Comprehensive error handling with retries
- ✅ DynamoDB result storage with TTL

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `BEDROCK_AGENT_ID` | Bedrock Agent ID | `ASPMAO88W7` |
| `BEDROCK_AGENT_ALIAS_ID` | Agent Alias ID | `I2FYS2ELU3` |
| `BEDROCK_REGION` | AWS region for Bedrock | `us-east-1` |
| `API_GATEWAY_BASE_URL` | API Gateway base URL | `https://xxxxx.execute-api.us-east-1.amazonaws.com` |
| `DYNAMODB_TABLE_NAME` | SearchResults table name | `SearchResults` |
| `DYNAMODB_REGION` | DynamoDB region | `eu-north-1` |
| `APPSYNC_ENDPOINT` | AppSync GraphQL endpoint | `https://xxxxx.appsync-api.us-east-1.amazonaws.com/graphql` |
| `APPSYNC_API_KEY` | AppSync API key | `da2-xxxxxxxxxxxxx` |

## IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeAgent"
      ],
      "Resource": "arn:aws:bedrock:us-east-1:ACCOUNT_ID:agent/AGENT_ID"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem"
      ],
      "Resource": "arn:aws:dynamodb:eu-north-1:ACCOUNT_ID:table/SearchResults"
    },
    {
      "Effect": "Allow",
      "Action": "appsync:GraphQL",
      "Resource": "arn:aws:appsync:us-east-1:ACCOUNT_ID:apis/API_ID/*"
    },
    {
      "Effect": "Allow",
      "Action": "logs:*",
      "Resource": "*"
    }
  ]
}
```

## Input Event

Invoked by InvokerLambda with the following payload:

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

## Output

Returns status response:

```json
{
  "statusCode": 200,
  "body": "{\"searchId\": \"search_1234567890_abc123\", \"status\": \"complete\", \"hospitals\": 5}"
}
```

## AppSync Streaming

The function publishes agent activity chunks to AppSync in real-time:

1. **Initial Status**: `🚀 Starting AI-powered hospital search...`
2. **Agent Traces**: 
   - `💭 Analyzing your requirements...`
   - `🤔 Agent thinking...`
   - `🔍 Searching database...`
   - `✓ Model responded`
3. **Enrichment**: `📊 Enriching data for 5 hospitals...`
4. **Completion**: `✅ Search completed! Found 5 hospitals.`

## Deployment

### 1. Install Dependencies

```bash
cd aws/lambda/searchWorkerFunction
pip install -r requirements.txt -t .
```

### 2. Create Deployment Package

**Windows (PowerShell):**
```powershell
Compress-Archive -Path * -DestinationPath searchWorkerFunction.zip -Force
```

**Linux/Mac:**
```bash
zip -r searchWorkerFunction.zip . -x "*.git*" "*.md" "test-event.json"
```

### 3. Deploy to AWS

```bash
aws lambda create-function \
  --function-name searchWorkerFunction \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-execution-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://searchWorkerFunction.zip \
  --timeout 60 \
  --memory-size 1024 \
  --environment Variables="{BEDROCK_AGENT_ID=ASPMAO88W7,BEDROCK_AGENT_ALIAS_ID=I2FYS2ELU3,BEDROCK_REGION=us-east-1,API_GATEWAY_BASE_URL=https://xxxxx.execute-api.us-east-1.amazonaws.com,DYNAMODB_TABLE_NAME=SearchResults,DYNAMODB_REGION=eu-north-1,APPSYNC_ENDPOINT=https://xxxxx.appsync-api.us-east-1.amazonaws.com/graphql,APPSYNC_API_KEY=da2-xxxxx}"
```

### 4. Update Existing Function

```bash
aws lambda update-function-code \
  --function-name searchWorkerFunction \
  --zip-file fileb://searchWorkerFunction.zip
```

## Testing

### Local Testing

```bash
# Test with sample event
aws lambda invoke \
  --function-name searchWorkerFunction \
  --payload file://test-event.json \
  --cli-binary-format raw-in-base64-out \
  response.json

# View response
cat response.json
```

### Monitor Logs

```bash
# Tail logs
aws logs tail /aws/lambda/searchWorkerFunction --follow

# Filter for specific search
aws logs filter-log-events \
  --log-group-name /aws/lambda/searchWorkerFunction \
  --filter-pattern "search_1234567890"
```

## Troubleshooting

### Issue: AppSync publish fails

**Symptoms**: Logs show "AppSync publish error"

**Solution**:
1. Verify `APPSYNC_ENDPOINT` and `APPSYNC_API_KEY` are correct
2. Check IAM permissions for `appsync:GraphQL`
3. Verify AppSync API is deployed and active

### Issue: Bedrock Agent timeout

**Symptoms**: "Empty response from Bedrock Agent"

**Solution**:
1. Increase Lambda timeout to 60 seconds
2. Check Bedrock Agent is active and accessible
3. Verify `BEDROCK_AGENT_ID` and `BEDROCK_AGENT_ALIAS_ID`

### Issue: No hospitals found

**Symptoms**: "LLM returned no hospitals"

**Solution**:
1. Check Bedrock Agent configuration
2. Verify action groups are properly configured
3. Test query with Bedrock Agent console

### Issue: DynamoDB write fails

**Symptoms**: "Failed to save search results"

**Solution**:
1. Verify `DYNAMODB_TABLE_NAME` and `DYNAMODB_REGION`
2. Check IAM permissions for `dynamodb:PutItem`
3. Verify table exists and is active

## Performance

- **Cold Start**: ~2-3 seconds
- **Warm Execution**: ~15-30 seconds (depends on Bedrock Agent)
- **Memory Usage**: ~512-768 MB
- **Concurrent Executions**: Supports up to 100

## Monitoring

### CloudWatch Metrics

- `Duration`: Execution time
- `Errors`: Error count
- `Throttles`: Throttle count
- `ConcurrentExecutions`: Concurrent invocations

### Custom Logs

- `Worker Lambda started`: Invocation start
- `Bedrock Agent response received`: Agent completion
- `Storing results`: DynamoDB write
- `Worker completed successfully`: Success
- `Worker failed`: Error

## Next Steps

1. Deploy InvokerLambda
2. Configure AppSync resolvers
3. Test end-to-end flow
4. Monitor CloudWatch logs
5. Optimize performance based on metrics
