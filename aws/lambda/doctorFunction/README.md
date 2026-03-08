# Doctor Function - Lambda Documentation

## Overview

The **doctorFunction** manages doctor profiles and information in the Hospital Review Platform. It provides CRUD operations for doctor data, including specializations, departments, hospitals, and ratings.

## Purpose

This function maintains the doctor database, which is essential for:
- Storing doctor profiles and credentials
- Managing doctor-hospital-department relationships
- Tracking doctor ratings and reviews
- Enabling doctor-specific searches
- Supporting AI-powered doctor recommendations

## API Endpoints

### 1. Create Doctor
**Endpoint**: `POST /doctors`

**Request Body**:
```json
{
  "doctorName": "Dr. Sarah Johnson",
  "specialization": "Cardiologist",
  "hospitalId": "hosp_001",
  "departmentId": "dept_001",
  "rating": 4.8,
  "experience": 15,
  "qualifications": ["MD", "FACC"],
  "consultationFee": 500
}
```

### 2. List Doctors
**Endpoint**: `GET /doctors?limit=10&hospitalId=hosp_001`

### 3. Get Doctor by ID
**Endpoint**: `GET /doctors/{doctorId}`

### 4. Update Doctor
**Endpoint**: `PUT /doctors/{doctorId}`

### 5. Delete Doctor
**Endpoint**: `DELETE /doctors/{doctorId}`

## Data Model

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `doctorId` | String (PK) | Yes | Unique doctor identifier |
| `doctorName` | String | Yes | Full name with title |
| `specialization` | String | Yes | Medical specialty |
| `hospitalId` | String | Yes | Primary hospital ID |
| `departmentId` | String | Yes | Department ID |
| `rating` | Number | No | Average rating (0-5) |
| `experience` | Number | No | Years of experience |
| `qualifications` | List<String> | No | Degrees and certifications |
| `consultationFee` | Number | No | Fee in local currency |
| `createdAt` | String | Yes | ISO-8601 timestamp |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TABLE_NAME` | `Doctor` | DynamoDB table name |
| `DYNAMODB_REGION` | `eu-north-1` | AWS region |

## Configuration

- **Memory**: 256 MB
- **Timeout**: 10 seconds
- **Runtime**: Python 3.11

## Related Functions

- **hospitalFunction**: Hospital associations
- **departmentFunction**: Department assignments
- **searchFunction**: Doctor-based hospital search
- **reviewFunction**: Doctor reviews and ratings

---

**Last Updated**: March 8, 2026  
**Version**: 1.0.0
