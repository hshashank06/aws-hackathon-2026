# Health Search Tool Function - Lambda Documentation

## Overview

The **healthSearchToolFunction** is a specialized Lambda function that serves as the action group for AWS Bedrock Agent. It provides intelligent database query capabilities for AI-powered hospital search and recommendations.

## Purpose

This function acts as the "brain" behind the AI agent, providing:
- Complex database queries for hospital search
- Doctor specialization lookups
- Insurance-based hospital filtering
- Cost-based hospital recommendations
- Top doctor identification by department

## Architecture

### Technology Stack
- **Runtime**: Python 3.11
- **Database**: Amazon DynamoDB
- **AI Integration**: AWS Bedrock Agent (Action Group)
- **Query Engine**: boto3 DynamoDB queries with complex filtering

### Integration Points
- **Bedrock Agent**: Receives function calls from AI agent
- **DynamoDB**: Queries Hospital, Doctor, InsuranceCompany tables
- **searchWorkerFunction**: Provides data for AI-powered search

## Available Functions

### 1. get_all_insurance_companies
**Purpose**: Retrieve all insurance companies

**Parameters**: None

**Returns**:
```json
{
  "insuranceCompanies": [
    {
      "insuranceCompanyId": "ins_001",
      "insuranceCompanyName": "Blue Cross Blue Shield"
    }
  ]
}
```

### 2. get_hospitals_by_affordability
**Purpose**: Find hospitals within a cost range

**Parameters**:
- `minCost` (number): Minimum treatment cost
- `maxCost` (number): Maximum treatment cost

**Returns**: List of hospitals with costs in range

### 3. get_hospitals_by_insurance
**Purpose**: Find hospitals accepting specific insurance

**Parameters**:
- `insuranceCompanyId` (string): Insurance company ID

**Returns**: List of hospitals accepting the insurance

### 4. get_hospitals_by_insurance_name
**Purpose**: Find hospitals by insurance company name

**Parameters**:
- `insuranceCompanyName` (string): Insurance company name

**Returns**: List of hospitals accepting the insurance

### 5. get_hospitals_with_high_insurance_coverage
**Purpose**: Find hospitals with high insurance coverage

**Parameters**:
- `minCoverage` (number): Minimum coverage percentage (0-1)

**Returns**: List of hospitals with coverage >= minCoverage

### 6. get_hospitals_with_top_doctors_in_department
**Purpose**: Find hospitals with top-rated doctors in a department

**Parameters**:
- `departmentName` (string): Department name (e.g., "Cardiology")
- `minRating` (number): Minimum doctor rating (0-5)

**Returns**: List of hospitals with top doctors

### 7. get_hospitals_by_surgery_cost
**Purpose**: Find hospitals by surgery cost range

**Parameters**:
- `surgeryType` (string): Type of surgery
- `maxCost` (number): Maximum cost

**Returns**: List of hospitals within budget

### 8. get_doctors_by_specialization
**Purpose**: Find doctors by specialization

**Parameters**:
- `specialization` (string): Medical specialty

**Returns**: List of doctors with that specialization

### 9. get_hospital_id_by_name
**Purpose**: Get hospital ID from name

**Parameters**:
- `hospitalName` (string): Hospital name

**Returns**: Hospital ID

### 10. get_doctor_id_by_name
**Purpose**: Get doctor ID from name

**Parameters**:
- `doctorName` (string): Doctor name

**Returns**: Doctor ID

### 11. get_hospital_doctors
**Purpose**: Get all doctors in a hospital

**Parameters**:
- `hospitalId` (string): Hospital ID

**Returns**: List of doctors in the hospital

## Function Call Format

### Bedrock Agent Request

```json
{
  "messageVersion": "1.0",
  "agent": {
    "name": "HealthSearchAgent",
    "id": "ASPMAO88W7",
    "alias": "BXNC6XCUEC",
    "version": "1"
  },
  "actionGroup": "HealthSearchTools",
  "function": "get_hospitals_by_insurance_name",
  "parameters": [
    {
      "name": "insuranceCompanyName",
      "type": "string",
      "value": "Blue Cross"
    }
  ]
}
```

### Lambda Response

```json
{
  "messageVersion": "1.0",
  "response": {
    "actionGroup": "HealthSearchTools",
    "function": "get_hospitals_by_insurance_name",
    "functionResponse": {
      "responseBody": {
        "TEXT": {
          "body": "{\"hospitals\": [{\"hospitalId\": \"hosp_001\", \"hospitalName\": \"Apollo Hospitals\"}]}"
        }
      }
    }
  }
}
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HOSPITAL_TABLE` | No | `Hospital` | Hospital table name |
| `DOCTOR_TABLE` | No | `Doctor` | Doctor table name |
| `DEPARTMENT_TABLE` | No | `Department` | Department table name |
| `INSURANCE_COMPANY_TABLE` | No | `InsuranceCompany` | Insurance company table name |
| `DYNAMODB_REGION` | No | `eu-north-1` | AWS region |

## Configuration

### IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:Scan",
        "dynamodb:Query",
        "dynamodb:GetItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:eu-north-1:*:table/Hospital",
        "arn:aws:dynamodb:eu-north-1:*:table/Doctor",
        "arn:aws:dynamodb:eu-north-1:*:table/Department",
        "arn:aws:dynamodb:eu-north-1:*:table/InsuranceCompany"
      ]
    }
  ]
}
```

### Lambda Configuration

- **Memory**: 512 MB (complex queries)
- **Timeout**: 30 seconds (multiple table scans)
- **Runtime**: Python 3.11
- **Handler**: `lambda_function.lambda_handler`

## Testing

### Test Event (Get Hospitals by Insurance)

```json
{
  "messageVersion": "1.0",
  "agent": {
    "name": "HealthSearchAgent",
    "id": "ASPMAO88W7",
    "alias": "BXNC6XCUEC",
    "version": "1"
  },
  "actionGroup": "HealthSearchTools",
  "function": "get_hospitals_by_insurance_name",
  "parameters": [
    {
      "name": "insuranceCompanyName",
      "type": "string",
      "value": "Blue Cross"
    }
  ]
}
```

### Test Event (Get Doctors by Specialization)

```json
{
  "messageVersion": "1.0",
  "actionGroup": "HealthSearchTools",
  "function": "get_doctors_by_specialization",
  "parameters": [
    {
      "name": "specialization",
      "type": "string",
      "value": "Cardiologist"
    }
  ]
}
```

## Performance

### Benchmarks

- **Simple Queries** (get by ID): 100-200ms
- **Scan Operations** (filter by attribute): 500-1500ms
- **Complex Queries** (multiple tables): 1000-3000ms

### Optimization

1. **Caching**: Cache frequently accessed data
2. **Indexes**: Use GSI for common query patterns
3. **Parallel Queries**: Use ThreadPoolExecutor for multiple tables
4. **Projection**: Fetch only required attributes

## Monitoring

### CloudWatch Logs

Log group: `/aws/lambda/healthSearchToolFunction`

**Sample Logs**:
```
[INFO] Function invoked | Function=get_hospitals_by_insurance_name | Params={'insuranceCompanyName': 'Blue Cross'}
[INFO] Scanning InsuranceCompany table | Filter=insuranceCompanyName contains Blue Cross
[INFO] Found insurance company | CompanyId=ins_001 | Name=Blue Cross Blue Shield
[INFO] Scanning Hospital table | Filter=insuranceCompanyIds contains ins_001
[INFO] Found 15 hospitals | Duration=850ms
```

### Key Metrics

- **Invocations**: ~1000/day (via Bedrock Agent)
- **Average Duration**: 800ms
- **Error Rate**: <2%
- **Throttles**: 0

## Error Handling

### Common Errors

**InvalidParameterException**: Missing required parameter
```json
{
  "error": "Missing required parameter: insuranceCompanyName"
}
```

**ResourceNotFoundException**: Table not found
```json
{
  "error": "Hospital table not found"
}
```

**ValidationException**: Invalid parameter value
```json
{
  "error": "minCoverage must be between 0 and 1"
}
```

## Integration with Bedrock Agent

### Action Group Configuration

**Action Group Name**: `HealthSearchTools`

**OpenAPI Schema**: See `aws/agents/action-groups/all-functions.json`

**Invocation**: Bedrock Agent calls this Lambda when user queries require database lookups

### Example User Queries

1. "Find hospitals that accept Blue Cross insurance"
   → Calls `get_hospitals_by_insurance_name`

2. "Show me cardiologists in Apollo Hospital"
   → Calls `get_hospital_id_by_name` + `get_hospital_doctors`

3. "Which hospitals have top-rated neurologists?"
   → Calls `get_hospitals_with_top_doctors_in_department`

4. "Find affordable hospitals for cardiac surgery"
   → Calls `get_hospitals_by_surgery_cost`

## Related Functions

- **searchWorkerFunction**: Uses this function via Bedrock Agent
- **searchFunction**: Alternative search implementation
- **hospitalFunction**: Data source for hospital queries
- **doctorFunction**: Data source for doctor queries
- **insuranceCompanyFunction**: Data source for insurance queries

## Changelog

### Version 1.0.0 (2024-03-08)
- Initial release
- 11 search functions
- Bedrock Agent integration
- Multi-table query support

---

**Last Updated**: March 8, 2026  
**Version**: 1.0.0  
**Maintainer**: Hospital Review Platform Team
