# Insurance Company Function - Lambda Documentation

## Overview

The **insuranceCompanyFunction** manages insurance company data in the Hospital Review Platform. It provides CRUD operations for insurance providers and their service offerings.

## Purpose

Manages insurance company profiles for:
- Storing insurance provider information
- Tracking company services and coverage
- Supporting insurance-based hospital search
- Enabling policy management

## API Endpoints

### 1. Create Insurance Company
**Endpoint**: `POST /insurance-companies`

**Request Body**:
```json
{
  "insuranceCompanyName": "Blue Cross Blue Shield",
  "description": "Leading health insurance provider",
  "services": "Comprehensive health coverage, dental, vision"
}
```

### 2. List Insurance Companies
**Endpoint**: `GET /insurance-companies?limit=50`

### 3. Get Insurance Company by ID
**Endpoint**: `GET /insurance-companies/{insuranceCompanyId}`

### 4. Update Insurance Company
**Endpoint**: `PUT /insurance-companies/{insuranceCompanyId}`

### 5. Delete Insurance Company
**Endpoint**: `DELETE /insurance-companies/{insuranceCompanyId}`

## Data Model

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `insuranceCompanyId` | String (PK) | Yes | Unique company identifier |
| `insuranceCompanyName` | String | Yes | Company name |
| `description` | String | Yes | Company description |
| `services` | String | Yes | Services offered |
| `createdAt` | String | Yes | ISO-8601 timestamp |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TABLE_NAME` | `InsuranceCompany` | DynamoDB table name |
| `DYNAMODB_REGION` | `eu-north-1` | AWS region |

## Configuration

- **Memory**: 256 MB
- **Timeout**: 10 seconds
- **Runtime**: Python 3.11

## Related Functions

- **insurancePolicyFunction**: Manages policies for companies
- **hospitalFunction**: Hospital-insurance partnerships
- **searchFunction**: Insurance-based hospital search
- **healthSearchToolFunction**: AI-powered insurance queries

---

**Last Updated**: March 8, 2026  
**Version**: 1.0.0
