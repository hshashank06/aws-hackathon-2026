# Insurance Policy Function - Lambda Documentation

## Overview

The **insurancePolicyFunction** manages insurance policies in the Hospital Review Platform. It provides CRUD operations for individual insurance plans offered by insurance companies.

## Purpose

Manages insurance policy details for:
- Storing policy information and coverage details
- Linking policies to insurance companies
- Supporting customer policy assignments
- Enabling policy-based hospital recommendations

## API Endpoints

### 1. Create Insurance Policy
**Endpoint**: `POST /insurance-policies`

**Request Body**:
```json
{
  "companyId": "ins_comp_001",
  "about": "# Gold Plan\n\n- Coverage: $500,000\n- Deductible: $1,000\n- Co-pay: 20%"
}
```

### 2. List Insurance Policies
**Endpoint**: `GET /insurance-policies?companyId=ins_comp_001&limit=20`

**Query Parameters**:
- `limit`: Number of items to return
- `lastKey`: Pagination token
- `companyId`: Filter by insurance company

### 3. Get Insurance Policy by ID
**Endpoint**: `GET /insurance-policies/{policyId}`

### 4. Update Insurance Policy
**Endpoint**: `PUT /insurance-policies/{policyId}`

### 5. Delete Insurance Policy
**Endpoint**: `DELETE /insurance-policies/{policyId}`

## Data Model

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `policyId` | String (PK) | Yes | Unique policy identifier |
| `companyId` | String | Yes | Insurance company ID (FK) |
| `about` | String | Yes | Markdown description of plan |
| `createdAt` | String | Yes | ISO-8601 timestamp |

### Policy Description Format

The `about` field uses Markdown format for rich text:

```markdown
# Gold Plan

## Coverage Details
- Maximum Coverage: $500,000
- Annual Deductible: $1,000
- Co-payment: 20%
- Out-of-pocket Maximum: $5,000

## Covered Services
- Hospitalization
- Surgery
- Emergency Care
- Prescription Drugs
- Preventive Care

## Exclusions
- Cosmetic procedures
- Experimental treatments
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TABLE_NAME` | `InsurancePolicy` | DynamoDB table name |
| `DYNAMODB_REGION` | `eu-north-1` | AWS region |

## Configuration

- **Memory**: 256 MB
- **Timeout**: 10 seconds
- **Runtime**: Python 3.11

## Testing

### Test Event (Create Policy)

```json
{
  "httpMethod": "POST",
  "path": "/insurance-policies",
  "body": "{\"companyId\":\"ins_comp_001\",\"about\":\"# Basic Plan\\n\\n- Coverage: $100,000\"}"
}
```

### Test Event (List by Company)

```json
{
  "httpMethod": "GET",
  "path": "/insurance-policies",
  "queryStringParameters": {
    "companyId": "ins_comp_001",
    "limit": "10"
  }
}
```

## Related Functions

- **insuranceCompanyFunction**: Parent company management
- **customerFunction**: Customer policy assignments
- **searchFunction**: Policy-based hospital search
- **reviewFunction**: Insurance claim tracking

---

**Last Updated**: March 8, 2026  
**Version**: 1.0.0
