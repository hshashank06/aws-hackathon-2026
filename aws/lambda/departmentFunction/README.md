# Department Function - Lambda Documentation

## Overview

The **departmentFunction** is an AWS Lambda function that manages hospital departments in the Hospital Review Platform. It provides CRUD operations for department data, including department information, associated doctors, and hospital relationships.

## Purpose

This function manages the organizational structure of hospitals by maintaining department records. Each department belongs to a specific hospital and contains a list of doctors who work in that department. This is crucial for:
- Organizing hospital services by specialty
- Routing patients to appropriate departments
- Managing doctor assignments
- Enabling department-specific searches

## Architecture

### Technology Stack
- **Runtime**: Python 3.11
- **Database**: Amazon DynamoDB
- **API**: AWS API Gateway (HTTP/REST API)
- **Authentication**: IAM-based

### Integration Points
- **API Gateway**: HTTP request routing
- **DynamoDB**: Department data storage
- **hospitalFunction**: Parent hospital relationship
- **doctorFunction**: Doctor assignments
- **searchFunction**: Department-based hospital search

## API Endpoints

### 1. Create Department
**Endpoint**: `POST /departments`

**Request Body**:
```json
{
  "departmentName": "Cardiology",
  "departmentDescription": "Heart and cardiovascular care",
  "hospitalId": "hosp_001",
  "listOfDoctorIds": ["doc_001", "doc_002"]
}
```

**Response** (201 Created):
```json
{
  "departmentId": "dept_1234567890_abc123",
  "departmentName": "Cardiology",
  "departmentDescription": "Heart and cardiovascular care",
  "hospitalId": "hosp_001",
  "listOfDoctorIds": ["doc_001", "doc_002"],
  "createdAt": "2024-03-08T10:30:45.123Z"
}
```

### 2. List Departments
**Endpoint**: `GET /departments`

**Query Parameters**:
- `limit` (optional): Number of items to return (default: 100)
- `lastKey` (optional): Pagination token
- `hospitalId` (optional): Filter by hospital ID

**Response** (200 OK):
```json
{
  "items": [
    {
      "departmentId": "dept_001",
      "departmentName": "Cardiology",
      "hospitalId": "hosp_001",
      "listOfDoctorIds": ["doc_001", "doc_002"]
    }
  ],
  "lastKey": "eyJkZXBhcnRtZW50SWQiOiAiZGVwdF8wMDEifQ=="
}
```

### 3. Get Department by ID
**Endpoint**: `GET /departments/{departmentId}`

**Response** (200 OK):
```json
{
  "departmentId": "dept_001",
  "departmentName": "Cardiology",
  "departmentDescription": "Heart and cardiovascular care",
  "hospitalId": "hosp_001",
  "listOfDoctorIds": ["doc_001", "doc_002", "doc_003"],
  "createdAt": "2024-03-08T10:30:45.123Z"
}
```

### 4. Update Department
**Endpoint**: `PUT /departments/{departmentId}`

**Request Body**:
```json
{
  "departmentDescription": "Advanced cardiac care and surgery",
  "listOfDoctorIds": ["doc_001", "doc_002", "doc_003", "doc_004"]
}
```

**Response** (200 OK):
```json
{
  "departmentId": "dept_001",
  "departmentName": "Cardiology",
  "departmentDescription": "Advanced cardiac care and surgery",
  "listOfDoctorIds": ["doc_001", "doc_002", "doc_003", "doc_004"],
  "updatedAt": "2024-03-08T11:00:00.000Z"
}
```

### 5. Delete Department
**Endpoint**: `DELETE /departments/{departmentId}`

**Response** (200 OK):
```json
{
  "message": "Department deleted successfully",
  "departmentId": "dept_001"
}
```

## Data Model

### Department Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `departmentId` | String (PK) | Yes | Unique department identifier (auto-generated) |
| `departmentName` | String | Yes | Name of the department (e.g., "Cardiology") |
| `departmentDescription` | String | Yes | Description of services offered |
| `hospitalId` | String | Yes | Hospital ID (FK → Hospital) |
| `listOfDoctorIds` | List<String> | No | Array of doctor IDs in this department |
| `createdAt` | String | Yes | ISO-8601 timestamp (auto-generated) |

### Common Department Names

- Cardiology
- Neurology
- Orthopedics
- Pediatrics
- Oncology
- Emergency Medicine
- Radiology
- Pathology

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TABLE_NAME` | No | `Department` | DynamoDB table name |
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
      "Resource": "arn:aws:dynamodb:eu-north-1:*:table/Department"
    }
  ]
}
```

### Lambda Configuration

- **Memory**: 256 MB
- **Timeout**: 10 seconds
- **Runtime**: Python 3.11
- **Handler**: `lambda_function.lambda_handler`

## Testing

### Test Event (Create Department)

```json
{
  "httpMethod": "POST",
  "path": "/departments",
  "body": "{\"departmentName\":\"Cardiology\",\"departmentDescription\":\"Heart care\",\"hospitalId\":\"hosp_001\"}"
}
```

### Test Event (List by Hospital)

```json
{
  "httpMethod": "GET",
  "path": "/departments",
  "queryStringParameters": {
    "hospitalId": "hosp_001",
    "limit": "10"
  }
}
```

## Deployment

```bash
# Package and deploy
zip -r function.zip lambda_function.py

aws lambda update-function-code \
  --function-name departmentFunction \
  --zip-file fileb://function.zip
```

## Monitoring

### CloudWatch Logs
Log group: `/aws/lambda/departmentFunction`

### Key Metrics
- Average latency: ~150ms
- P99 latency: ~500ms
- Error rate: <1%

## Related Functions

- **hospitalFunction**: Parent hospital management
- **doctorFunction**: Doctor assignments
- **searchFunction**: Department-based search
- **healthSearchToolFunction**: AI-powered department search

---

**Last Updated**: March 8, 2026  
**Version**: 1.0.0
