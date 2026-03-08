# Hospital Function - Lambda Documentation

## Overview

The **hospitalFunction** manages hospital data in the Hospital Review Platform. It provides CRUD operations for hospital information, including location, services, departments, and insurance partnerships.

## Purpose

This function is the core of the hospital database, managing:
- Hospital profiles and contact information
- Geographic location data (lat/lon coordinates)
- Services and specialties offered
- Department and insurance company relationships
- Hospital ratings and statistics

## API Endpoints

### 1. Create Hospital
**Endpoint**: `POST /hospitals`

**Request Body**:
```json
{
  "hospitalName": "Apollo Hospitals",
  "address": "Jubilee Hills, Hyderabad, Telangana, India",
  "location": "17.4122, 78.4071",
  "phoneNumber": "+91-40-23607777",
  "services": ["Cardiology", "Neurology", "Orthopedics"],
  "departmentIds": ["dept_001", "dept_002"],
  "insuranceCompanyIds": ["ins_001", "ins_002"]
}
```

**Response** (201 Created):
```json
{
  "hospitalId": "hosp_1234567890_abc123",
  "hospitalName": "Apollo Hospitals",
  "address": "Jubilee Hills, Hyderabad, Telangana, India",
  "location": "17.4122, 78.4071",
  "phoneNumber": "+91-40-23607777",
  "services": ["Cardiology", "Neurology", "Orthopedics"],
  "departmentIds": ["dept_001", "dept_002"],
  "insuranceCompanyIds": ["ins_001", "ins_002"],
  "rating": 0,
  "minCost": 0,
  "maxCost": 0,
  "insuranceCoverage": 0,
  "createdAt": "2024-03-08T10:30:45.123Z"
}
```

### 2. List Hospitals
**Endpoint**: `GET /hospitals?limit=20`

**Response** (200 OK):
```json
{
  "items": [
    {
      "hospitalId": "hosp_001",
      "hospitalName": "Apollo Hospitals",
      "location": "17.4122, 78.4071",
      "rating": 4.5,
      "services": ["Cardiology", "Neurology"]
    }
  ],
  "lastKey": "eyJob3NwaXRhbElkIjogImhvc3BfMDAxIn0="
}
```

### 3. Get Hospital by ID
**Endpoint**: `GET /hospitals/{hospitalId}`

**Response** (200 OK):
```json
{
  "hospitalId": "hosp_001",
  "hospitalName": "Apollo Hospitals",
  "address": "Jubilee Hills, Hyderabad, Telangana, India",
  "location": "17.4122, 78.4071",
  "phoneNumber": "+91-40-23607777",
  "services": ["Cardiology", "Neurology", "Orthopedics", "Oncology"],
  "departmentIds": ["dept_001", "dept_002", "dept_003"],
  "insuranceCompanyIds": ["ins_001", "ins_002", "ins_003"],
  "rating": 4.5,
  "minCost": 5000,
  "maxCost": 500000,
  "insuranceCoverage": 0.75,
  "description": "Leading multi-specialty hospital",
  "createdAt": "2024-03-08T10:30:45.123Z"
}
```

### 4. Update Hospital
**Endpoint**: `PUT /hospitals/{hospitalId}`

**Request Body**:
```json
{
  "phoneNumber": "+91-40-23607778",
  "services": ["Cardiology", "Neurology", "Orthopedics", "Oncology", "Pediatrics"],
  "rating": 4.6
}
```

### 5. Delete Hospital
**Endpoint**: `DELETE /hospitals/{hospitalId}`

## Data Model

### Hospital Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `hospitalId` | String (PK) | Yes | Unique hospital identifier |
| `hospitalName` | String | Yes | Official hospital name |
| `address` | String | Yes | Full address |
| `location` | String | Yes | "latitude, longitude" format |
| `phoneNumber` | String | Yes | Contact number |
| `services` | List<String> | Yes | Medical services offered |
| `departmentIds` | List<String> | No | Department IDs |
| `insuranceCompanyIds` | List<String> | No | Accepted insurance companies |
| `rating` | Number | No | Average rating (0-5) |
| `minCost` | Number | No | Minimum treatment cost |
| `maxCost` | Number | No | Maximum treatment cost |
| `insuranceCoverage` | Number | No | Coverage percentage (0-1) |
| `description` | String | No | Hospital description |
| `createdAt` | String | Yes | ISO-8601 timestamp |

### Location Format

The `location` field stores coordinates as a comma-separated string:
```
"latitude, longitude"
Example: "17.4122, 78.4071"
```

This format is used for:
- Distance calculations in search results
- Map display in the UI
- Proximity-based hospital recommendations

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TABLE_NAME` | No | `Hospital` | DynamoDB table name |
| `DYNAMODB_REGION` | No | `eu-north-1` | AWS region for DynamoDB |

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
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:eu-north-1:*:table/Hospital"
    }
  ]
}
```

### Lambda Configuration

- **Memory**: 512 MB (higher due to complex data structures)
- **Timeout**: 15 seconds
- **Runtime**: Python 3.11
- **Handler**: `lambda_function.lambda_handler`

## Testing

### Test Event (Create Hospital)

```json
{
  "httpMethod": "POST",
  "path": "/hospitals",
  "body": "{\"hospitalName\":\"Test Hospital\",\"address\":\"Test Address\",\"location\":\"17.4122, 78.4071\",\"phoneNumber\":\"+91-1234567890\",\"services\":[\"General\"]}"
}
```

### Test Event (Get Hospital)

```json
{
  "httpMethod": "GET",
  "path": "/hospitals/hosp_001",
  "pathParameters": {
    "hospitalId": "hosp_001"
  }
}
```

## Deployment

```bash
# Package function
zip -r function.zip lambda_function.py

# Deploy
aws lambda update-function-code \
  --function-name hospitalFunction \
  --zip-file fileb://function.zip

# Update configuration
aws lambda update-function-configuration \
  --function-name hospitalFunction \
  --environment Variables="{TABLE_NAME=Hospital,DYNAMODB_REGION=eu-north-1}" \
  --memory-size 512 \
  --timeout 15
```

## Monitoring

### CloudWatch Metrics

- **Invocations**: ~5000/day
- **Average Duration**: 200ms
- **Error Rate**: <0.5%
- **Throttles**: 0

### CloudWatch Logs

Log group: `/aws/lambda/hospitalFunction`

**Sample Logs**:
```
[INFO] Creating hospital | Name=Apollo Hospitals
[INFO] Hospital created | HospitalId=hosp_001
[INFO] Fetching hospital | HospitalId=hosp_001
[INFO] Hospital found | Name=Apollo Hospitals | Rating=4.5
```

## Performance

### Benchmarks

- **Create Hospital**: 180ms average
- **Get Hospital**: 120ms average
- **List Hospitals**: 250ms average (100 items)
- **Update Hospital**: 150ms average
- **Delete Hospital**: 140ms average

### Optimization

1. **Projection Expressions**: Fetch only required fields for list operations
2. **Caching**: Cache frequently accessed hospitals
3. **Batch Operations**: Use batch_get_item for multiple hospitals
4. **Indexes**: Create GSI for location-based queries

## Integration

### Used By

- **searchFunction**: Hospital search and recommendations
- **searchWorkerFunction**: AI-powered hospital enrichment
- **healthSearchToolFunction**: Bedrock Agent tool for hospital queries
- **reviewFunction**: Hospital review submissions
- **Frontend**: Hospital detail pages, search results

### Dependencies

- **departmentFunction**: Department relationships
- **insuranceCompanyFunction**: Insurance partnerships
- **doctorFunction**: Doctor assignments

## Error Handling

### Common Errors

**ValidationException**: Missing required fields
```json
{
  "error": "Missing required field: hospitalName"
}
```

**ResourceNotFoundException**: Hospital not found
```json
{
  "error": "Hospital not found"
}
```

**ConditionalCheckFailedException**: Hospital already exists
```json
{
  "error": "Hospital with this ID already exists"
}
```

## Security

### Data Sensitivity

- **Public Data**: Hospital name, address, phone, services
- **Operational Data**: Ratings, costs, insurance coverage
- **No PII**: This function does not handle patient data

### Best Practices

1. Validate all input data
2. Sanitize location coordinates
3. Limit list operations with pagination
4. Enable CloudTrail for audit logging
5. Use VPC endpoints for DynamoDB access

## Related Functions

- **departmentFunction**: Manages hospital departments
- **doctorFunction**: Manages hospital doctors
- **searchFunction**: Searches hospitals
- **reviewFunction**: Hospital reviews and ratings
- **healthSearchToolFunction**: AI-powered hospital search

## Changelog

### Version 1.0.0 (2024-03-08)
- Initial release
- CRUD operations for hospitals
- Location-based data storage
- Insurance and department relationships
- Rating and cost tracking

---

**Last Updated**: March 8, 2026  
**Version**: 1.0.0  
**Maintainer**: Hospital Review Platform Team
