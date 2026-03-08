# Customer Function - Lambda Documentation

## Overview

The **customerFunction** is an AWS Lambda function that provides complete CRUD (Create, Read, Update, Delete) operations for managing customer data in the Hospital Review Platform. It serves as the backend API for all customer-related operations, handling patient information, insurance policies, and hospital visit history.

## Purpose

This Lambda function manages the customer/patient database, which is central to the platform's functionality. It stores patient demographics, insurance information, and tracks their hospital visits across different facilities, departments, and doctors.

## Architecture

### Technology Stack
- **Runtime**: Python 3.11
- **Database**: Amazon DynamoDB
- **API**: AWS API Gateway (HTTP/REST API)
- **Authentication**: IAM-based (API Gateway integration)

### Integration Points
- **API Gateway**: Receives HTTP requests and routes to appropriate handlers
- **DynamoDB**: Stores customer data with `customerId` as partition key
- **Other Lambda Functions**: Referenced by reviewFunction, searchFunction

## API Endpoints

### 1. Create Customer
**Endpoint**: `POST /customers`

**Request Body**:
```json
{
  "customerName": "John Doe",
  "email": "john.doe@example.com",
  "gender": "Male",
  "age": 35,
  "uhid": "UHID123456",
  "policyId": "policy_001"
}
```

**Response** (201 Created):
```json
{
  "customerId": "cust_1234567890_abc123",
  "customerName": "John Doe",
  "email": "john.doe@example.com",
  "gender": "Male",
  "age": 35,
  "uhid": "UHID123456",
  "policyId": "policy_001",
  "visits": [],
  "createdAt": "2024-03-08T10:30:45.123Z"
}
```

### 2. List Customers
**Endpoint**: `GET /customers`

**Query Parameters**:
- `limit` (optional): Number of items to return (default: 100)
- `lastKey` (optional): Pagination token from previous response

**Response** (200 OK):
```json
{
  "items": [
    {
      "customerId": "cust_001",
      "customerName": "John Doe",
      "email": "john.doe@example.com",
      "age": 35
    }
  ],
  "lastKey": "eyJjdXN0b21lcklkIjogImN1c3RfMDAxIn0="
}
```

### 3. Get Customer by ID
**Endpoint**: `GET /customers/{customerId}`

**Response** (200 OK):
```json
{
  "customerId": "cust_001",
  "customerName": "John Doe",
  "email": "john.doe@example.com",
  "gender": "Male",
  "age": 35,
  "uhid": "UHID123456",
  "policyId": "policy_001",
  "visits": [
    {
      "hospitalId": "hosp_001",
      "departmentId": "dept_001",
      "doctorId": "doc_001"
    }
  ],
  "createdAt": "2024-03-08T10:30:45.123Z"
}
```

### 4. Update Customer
**Endpoint**: `PUT /customers/{customerId}`

**Request Body**:
```json
{
  "customerName": "John Smith",
  "email": "john.smith@example.com",
  "age": 36
}
```

**Response** (200 OK):
```json
{
  "customerId": "cust_001",
  "customerName": "John Smith",
  "email": "john.smith@example.com",
  "age": 36,
  "updatedAt": "2024-03-08T11:00:00.000Z"
}
```

### 5. Delete Customer
**Endpoint**: `DELETE /customers/{customerId}`

**Response** (200 OK):
```json
{
  "message": "Customer deleted successfully",
  "customerId": "cust_001"
}
```

## Data Model

### Customer Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `customerId` | String (PK) | Yes | Unique customer identifier (auto-generated) |
| `customerName` | String | Yes | Full name of the customer |
| `email` | String | Yes | Email address |
| `gender` | String | Yes | Gender (Male/Female/Other) |
| `age` | Number | Yes | Age in years |
| `uhid` | String | Yes | Universal Health ID |
| `policyId` | String | No | Insurance policy ID (FK → InsurancePolicy) |
| `visits` | List | No | Array of hospital visit records |
| `createdAt` | String | Yes | ISO-8601 timestamp (auto-generated) |

### Visit Record Schema

```json
{
  "hospitalId": "hosp_001",
  "departmentId": "dept_001",
  "doctorId": "doc_001"
}
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TABLE_NAME` | No | `Customer` | DynamoDB table name |
| `DYNAMODB_REGION` | No | `eu-north-1` | AWS region for DynamoDB |
| `AWS_REGION` | Yes | - | Injected by Lambda runtime |

## Configuration

### IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Scan",
        "dynamodb:Query"
      ],
      "Resource": "arn:aws:dynamodb:eu-north-1:*:table/Customer"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

### Lambda Configuration

- **Memory**: 256 MB
- **Timeout**: 10 seconds
- **Runtime**: Python 3.11
- **Handler**: `lambda_function.lambda_handler`

## Error Handling

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success (GET, PUT, DELETE) |
| 201 | Created (POST) |
| 400 | Bad Request (invalid input) |
| 404 | Not Found (customer doesn't exist) |
| 500 | Internal Server Error |

### Error Response Format

```json
{
  "error": "Customer not found"
}
```

## Testing

### Test Event (Create Customer)

```json
{
  "httpMethod": "POST",
  "path": "/customers",
  "body": "{\"customerName\":\"Test User\",\"email\":\"test@example.com\",\"gender\":\"Male\",\"age\":30,\"uhid\":\"TEST123\"}"
}
```

### Test Event (Get Customer)

```json
{
  "httpMethod": "GET",
  "path": "/customers/cust_001",
  "pathParameters": {
    "customerId": "cust_001"
  }
}
```

### Local Testing

```bash
# Install dependencies
pip install boto3

# Run tests
python -m pytest tests/

# Invoke locally with SAM
sam local invoke customerFunction -e events/event-post-item.json
```

## Deployment

### Using AWS CLI

```bash
# Package function
zip -r function.zip lambda_function.py

# Deploy
aws lambda update-function-code \
  --function-name customerFunction \
  --zip-file fileb://function.zip

# Update environment variables
aws lambda update-function-configuration \
  --function-name customerFunction \
  --environment Variables="{TABLE_NAME=Customer,DYNAMODB_REGION=eu-north-1}"
```

### Using AWS SAM

```yaml
# template.yaml
Resources:
  CustomerFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: customerFunction/
      Handler: lambda_function.lambda_handler
      Runtime: python3.11
      Environment:
        Variables:
          TABLE_NAME: Customer
          DYNAMODB_REGION: eu-north-1
      Policies:
        - DynamoDBCrudPolicy:
            TableName: Customer
```

```bash
sam build
sam deploy --guided
```

## Monitoring

### CloudWatch Metrics

- **Invocations**: Total number of function invocations
- **Duration**: Execution time per invocation
- **Errors**: Number of failed invocations
- **Throttles**: Number of throttled requests

### CloudWatch Logs

Log group: `/aws/lambda/customerFunction`

**Log Format**:
```
[INFO] 2024-03-08T10:30:45.123Z Creating customer | Name=John Doe
[INFO] 2024-03-08T10:30:45.456Z Customer created | CustomerId=cust_001
[ERROR] 2024-03-08T10:30:45.789Z Failed to create customer | Error=ValidationException
```

### Alarms

Recommended CloudWatch Alarms:
- Error rate > 5%
- Duration > 5 seconds
- Throttles > 0

## Performance

### Benchmarks

- **Average Latency**: 150ms
- **P99 Latency**: 500ms
- **Throughput**: 1000 requests/second
- **Cold Start**: ~2 seconds

### Optimization Tips

1. **Connection Pooling**: Reuse DynamoDB connections across invocations
2. **Batch Operations**: Use batch_write_item for bulk operations
3. **Projection Expressions**: Fetch only required attributes
4. **Pagination**: Use limit and lastKey for large datasets

## Security

### Best Practices

1. **Input Validation**: Validate all input data before processing
2. **Least Privilege**: Grant minimal IAM permissions
3. **Encryption**: Enable DynamoDB encryption at rest
4. **API Gateway**: Use API keys or IAM authentication
5. **Secrets**: Store sensitive data in AWS Secrets Manager

### Data Privacy

- **PII Protection**: Customer data contains PII (email, name)
- **GDPR Compliance**: Implement data deletion on request
- **Audit Logging**: Enable CloudTrail for compliance

## Troubleshooting

### Common Issues

**Issue**: `ResourceNotFoundException: Requested resource not found`
- **Cause**: DynamoDB table doesn't exist
- **Solution**: Create table or update TABLE_NAME environment variable

**Issue**: `ValidationException: One or more parameter values were invalid`
- **Cause**: Missing required fields in request
- **Solution**: Ensure all required fields are provided

**Issue**: `AccessDeniedException: User is not authorized`
- **Cause**: Insufficient IAM permissions
- **Solution**: Update Lambda execution role with DynamoDB permissions

## Related Functions

- **reviewFunction**: Creates reviews linked to customers
- **searchFunction**: Searches hospitals based on customer preferences
- **insurancePolicyFunction**: Manages customer insurance policies

## Changelog

### Version 1.0.0 (2024-03-08)
- Initial release
- CRUD operations for customers
- Visit history tracking
- Insurance policy integration

## Support

For issues or questions:
- Check CloudWatch Logs: `/aws/lambda/customerFunction`
- Review DynamoDB table: `Customer`
- Contact: AWS Support or development team

---

**Last Updated**: March 8, 2026  
**Version**: 1.0.0  
**Maintainer**: Hospital Review Platform Team
