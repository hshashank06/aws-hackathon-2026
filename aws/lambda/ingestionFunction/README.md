# Ingestion Function - Lambda Documentation

## Overview

The **ingestionFunction** is a critical Lambda function that ingests hospital review data into Amazon OpenSearch for vector-based semantic search. It generates embeddings using AWS Bedrock Titan and indexes reviews with rich metadata for AI-powered search capabilities.

## Purpose

This function powers the semantic search capabilities of the platform by:
- Ingesting reviews from DynamoDB into OpenSearch
- Generating 1024-dimensional embeddings using Bedrock Titan Embed Text v2
- Enriching reviews with hospital, doctor, and customer data
- Creating searchable vector indexes for AI-powered recommendations
- Supporting bulk ingestion for data migration

## Architecture

### Technology Stack
- **Runtime**: Python 3.11
- **Vector Database**: Amazon OpenSearch Service
- **Embedding Model**: AWS Bedrock Titan Embed Text v2 (1024 dimensions)
- **Source Database**: Amazon DynamoDB
- **Authentication**: AWS Signature Version 4 (IAM-based)

### Integration Points
- **DynamoDB**: Reads review, hospital, doctor, customer data
- **Bedrock**: Generates embeddings for semantic search
- **OpenSearch**: Stores vectors and metadata for search
- **Bedrock Agent**: Uses indexed data for knowledge base queries

## Key Features

### 1. Embedding Generation
- Uses Bedrock Titan Embed Text v2 model
- Generates 1024-dimensional normalized vectors
- Handles text truncation (25,000 character limit)
- Fallback to indexing without embeddings on failure

### 2. Data Enrichment
Combines data from multiple DynamoDB tables:
- **Review**: Core review data (rating, comments, costs)
- **Hospital**: Hospital name, location, services
- **Doctor**: Doctor name, specialization
- **Customer**: Customer name, demographics

### 3. Bulk Ingestion
- Supports batch processing of multiple reviews
- Parallel embedding generation
- Efficient bulk indexing to OpenSearch
- Progress tracking and error handling

## API Endpoints

### Single Review Ingestion
**Trigger**: DynamoDB Stream or Direct Invocation

**Event Format**:
```json
{
  "reviewId": "review_001"
}
```

### Bulk Ingestion
**Event Format**:
```json
{
  "reviewIds": ["review_001", "review_002", "review_003"]
}
```

## Data Flow

```
1. Lambda receives reviewId(s)
   ↓
2. Fetch review from DynamoDB Review table
   ↓
3. Enrich with hospital, doctor, customer data
   ↓
4. Generate embedding text from review content
   ↓
5. Call Bedrock Titan to generate 1024-dim vector
   ↓
6. Index document in OpenSearch with vector
   ↓
7. Return success/failure status
```

## OpenSearch Index Schema

### Index Name
`health-review-index`

### Document Structure

```json
{
  "reviewId": "review_001",
  "hospitalId": "hosp_001",
  "hospitalName": "Apollo Hospitals",
  "doctorId": "doc_001",
  "doctorName": "Dr. Sarah Johnson",
  "customerId": "cust_001",
  "customerName": "John Doe",
  "overallRating": 5,
  "hospitalReview": "Excellent care and facilities",
  "doctorReview": "Very knowledgeable and caring",
  "procedureType": "Cardiac Surgery",
  "payment": {
    "totalBillAmount": 150000,
    "insuranceClaimed": true
  },
  "claim": {
    "claimAmountApproved": 120000,
    "claimStatus": "Approved"
  },
  "embedding": [0.123, -0.456, 0.789, ...],  // 1024 dimensions
  "embedding_text": "Combined text used for embedding generation",
  "createdAt": "2024-03-08T10:30:45.123Z",
  "verified": true
}
```

### Vector Field Configuration

```json
{
  "mappings": {
    "properties": {
      "embedding": {
        "type": "knn_vector",
        "dimension": 1024,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "nmslib"
        }
      }
    }
  }
}
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DYNAMODB_REGION` | No | `eu-north-1` | DynamoDB region |
| `OPENSEARCH_ENDPOINT` | Yes | - | OpenSearch domain endpoint |
| `OPENSEARCH_REGION` | No | `us-east-1` | OpenSearch region |
| `BEDROCK_REGION` | No | `us-east-1` | Bedrock region |
| `INDEX_NAME` | No | `health-review-index` | OpenSearch index name |

## Configuration

### IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:eu-north-1:*:table/Review",
        "arn:aws:dynamodb:eu-north-1:*:table/Hospital",
        "arn:aws:dynamodb:eu-north-1:*:table/Doctor",
        "arn:aws:dynamodb:eu-north-1:*:table/Customer"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
    },
    {
      "Effect": "Allow",
      "Action": [
        "es:ESHttpPut",
        "es:ESHttpPost",
        "es:ESHttpGet"
      ],
      "Resource": "arn:aws:es:us-east-1:*:domain/health-review-vector-domain/*"
    }
  ]
}
```

### Lambda Configuration

- **Memory**: 1024 MB (embedding generation is memory-intensive)
- **Timeout**: 60 seconds (allows for multiple embeddings)
- **Runtime**: Python 3.11
- **Handler**: `lambda_function.lambda_handler`
- **VPC**: Optional (for private OpenSearch domains)

### Dependencies (requirements.txt)

```
boto3>=1.28.0
opensearch-py>=2.3.0
requests-aws4auth>=1.2.0
```

## Testing

### Test Event (Single Review)

```json
{
  "reviewId": "review_001"
}
```

### Test Event (Bulk Ingestion)

```json
{
  "reviewIds": [
    "review_001",
    "review_002",
    "review_003",
    "review_004",
    "review_005"
  ]
}
```

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run bulk ingestion script
python bulk_ingest.py

# Test single review
python -c "import lambda_function; lambda_function.lambda_handler({'reviewId': 'review_001'}, None)"
```

## Deployment

### Using AWS CLI

```bash
# Package function with dependencies
pip install -r requirements.txt -t package/
cp lambda_function.py package/
cd package
zip -r ../function.zip .
cd ..

# Deploy
aws lambda update-function-code \
  --function-name ingestionFunction \
  --zip-file fileb://function.zip

# Update configuration
aws lambda update-function-configuration \
  --function-name ingestionFunction \
  --environment Variables="{
    OPENSEARCH_ENDPOINT=search-health-review-vector-domain-xxx.us-east-1.es.amazonaws.com,
    OPENSEARCH_REGION=us-east-1,
    BEDROCK_REGION=us-east-1,
    INDEX_NAME=health-review-index
  }" \
  --memory-size 1024 \
  --timeout 60
```

## Bulk Ingestion Scripts

### bulk_ingest.py
Ingests all reviews from DynamoDB into OpenSearch

```bash
python bulk_ingest.py
```

### bulk_ingest_all.py
Comprehensive ingestion with progress tracking

```bash
python bulk_ingest_all.py
```

## Performance

### Benchmarks

- **Single Review Ingestion**: 2-3 seconds
  - DynamoDB fetch: 100ms
  - Embedding generation: 1.5-2s
  - OpenSearch indexing: 200ms

- **Bulk Ingestion** (100 reviews): 180-240 seconds
  - Parallel processing: 5 concurrent embeddings
  - Average: 2 seconds per review

### Optimization

1. **Batch Processing**: Process multiple reviews in parallel
2. **Connection Pooling**: Reuse OpenSearch connections
3. **Caching**: Cache hospital/doctor data for repeated reviews
4. **Text Truncation**: Limit embedding text to 25,000 characters
5. **Error Handling**: Continue on individual failures

## Monitoring

### CloudWatch Metrics

- **Invocations**: Number of ingestion requests
- **Duration**: Time per ingestion
- **Errors**: Failed ingestions
- **Bedrock Invocations**: Embedding generation calls

### CloudWatch Logs

Log group: `/aws/lambda/ingestionFunction`

**Sample Logs**:
```
[INFO] Initialized clients - DynamoDB: eu-north-1, OpenSearch: us-east-1, Bedrock: us-east-1
[INFO] Processing review | ReviewId=review_001
[INFO] Fetched review data | HospitalId=hosp_001 | DoctorId=doc_001
[INFO] Generated embedding with 1024 dimensions
[INFO] Indexed document in OpenSearch | ReviewId=review_001 | Duration=2.3s
[INFO] Successfully ingested review | ReviewId=review_001
```

### Alarms

Recommended CloudWatch Alarms:
- Error rate > 5%
- Duration > 50 seconds
- Bedrock throttling > 0
- OpenSearch connection failures > 0

## Error Handling

### Common Errors

**OpenSearchException**: Connection failed
```
Error: Unable to connect to OpenSearch domain
Solution: Check VPC configuration and security groups
```

**BedrockException**: Embedding generation failed
```
Error: Bedrock model invocation failed
Solution: Check IAM permissions and model availability
```

**ResourceNotFoundException**: Review not found
```
Error: Review not found in DynamoDB
Solution: Verify reviewId exists in Review table
```

### Retry Logic

- **Bedrock**: 3 retries with exponential backoff
- **OpenSearch**: 2 retries with 1-second delay
- **DynamoDB**: Automatic retries via boto3

## Security

### Data Sensitivity

- **PII**: Customer names, review comments
- **PHI**: Medical procedure types, health information
- **Financial**: Payment amounts, insurance claims

### Best Practices

1. **Encryption**: Enable encryption at rest for OpenSearch
2. **VPC**: Deploy in private VPC for sensitive data
3. **IAM**: Use least privilege permissions
4. **Audit**: Enable CloudTrail for compliance
5. **Anonymization**: Consider anonymizing PII before indexing

## Integration

### Used By

- **Bedrock Agent**: Knowledge base for semantic search
- **searchWorkerFunction**: AI-powered hospital recommendations
- **reviewFunction**: Triggers ingestion on new reviews

### Triggers

- **DynamoDB Streams**: Auto-ingest on new reviews
- **Manual Invocation**: Bulk data migration
- **Scheduled**: Periodic re-indexing

## Troubleshooting

### Issue: Embeddings not generated

**Symptoms**: Documents indexed without `embedding` field

**Causes**:
- Bedrock model unavailable
- Text too long (>25,000 chars)
- IAM permissions missing

**Solutions**:
1. Check Bedrock model availability in region
2. Verify IAM role has `bedrock:InvokeModel` permission
3. Review CloudWatch logs for specific errors

### Issue: OpenSearch indexing slow

**Symptoms**: Duration > 10 seconds per document

**Causes**:
- Network latency
- Large document size
- OpenSearch cluster overloaded

**Solutions**:
1. Deploy Lambda in same VPC as OpenSearch
2. Reduce document size (remove unnecessary fields)
3. Scale up OpenSearch cluster

## Related Functions

- **reviewFunction**: Creates reviews that trigger ingestion
- **searchWorkerFunction**: Uses indexed data for AI search
- **Bedrock Agent**: Queries OpenSearch knowledge base

## Changelog

### Version 1.0.0 (2024-03-08)
- Initial release
- Bedrock Titan Embed Text v2 integration
- OpenSearch vector indexing
- Bulk ingestion support
- Data enrichment from multiple tables

---

**Last Updated**: March 8, 2026  
**Version**: 1.0.0  
**Maintainer**: Hospital Review Platform Team
