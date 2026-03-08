import json
import boto3
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
import os
import logging
import time

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get DynamoDB region from environment variable, default to eu-north-1
DYNAMODB_REGION = os.environ.get('DYNAMODB_REGION', 'eu-north-1')

# Initialize DynamoDB resource with explicit region
dynamodb = boto3.resource('dynamodb', region_name=DYNAMODB_REGION)

logger.info(f"DynamoDB resource initialized for region: {DYNAMODB_REGION}")

# Table names
HOSPITAL_TABLE = dynamodb.Table('Hospital')
DEPARTMENT_TABLE = dynamodb.Table('Department')
DOCTOR_TABLE = dynamodb.Table('Doctor')
INSURANCE_COMPANY_TABLE = dynamodb.Table('InsuranceCompany')

class DecimalEncoder(json.JSONEncoder):
    """Helper class to convert Decimal to float for JSON serialization"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def clean_hospital_data(hospital):
    """
    Remove unnecessary fields from hospital data to reduce response size.
    Keeps only essential information for display.
    """
    # Fields to remove (large ID arrays that aren't needed in response)
    fields_to_remove = ['patients', 'departmentIds', 'insuranceCompanyIds']
    
    cleaned = hospital.copy()
    for field in fields_to_remove:
        cleaned.pop(field, None)
    
    return cleaned

def clean_doctor_data(doctor):
    """
    Remove unnecessary fields from doctor data to reduce response size.
    Returns only essential fields: ID, name, rating, specialization.
    """
    return {
        'doctorId': doctor.get('doctorId'),
        'doctorName': doctor.get('doctorName'),
        'rating': doctor.get('rating'),
        'specialization': doctor.get('specialization') or doctor.get('departmentName')
    }

def get_all_insurance_companies():
    """
    Returns all insurance companies in the system.
    
    Returns:
        List of all insurance companies with their IDs and names
    """
    start = time.time()
    try:
        response = INSURANCE_COMPANY_TABLE.scan(
            ProjectionExpression='insuranceCompanyId, insuranceCompanyName',
            Limit=10  # Only 10 insurance companies
        )
        companies = response.get('Items', [])
        
        # Return simplified data with just ID and name
        result = [{
            'insuranceCompanyId': company.get('insuranceCompanyId'),
            'insuranceCompanyName': company.get('insuranceCompanyName')
        } for company in companies]
        
        logger.info(f"get_all_insurance_companies execution time: {time.time() - start:.3f}s")
        return result
    except Exception as e:
        logger.error(f"get_all_insurance_companies execution time: {time.time() - start:.3f}s (failed)")
        raise Exception(f"Error fetching insurance companies: {str(e)}")

def get_hospitals_by_affordability(min_affordability=0.0, max_affordability=1.0):
    """
    Returns hospitals based on affordability score range.
    
    Args:
        min_affordability: Minimum affordability score (0.0 to 1.0)
        max_affordability: Maximum affordability score (0.0 to 1.0)
    
    Returns:
        List of hospitals matching the affordability criteria
    """
    start = time.time()
    try:
        # Convert float to Decimal for DynamoDB
        min_affordability = Decimal(str(min_affordability))
        max_affordability = Decimal(str(max_affordability))
        
        response = HOSPITAL_TABLE.scan(
            FilterExpression=Attr('affordability').between(min_affordability, max_affordability),
            ProjectionExpression='hospitalId, hospitalName, rating, affordability, avgCost, minCost, maxCost, #loc, address',
            ExpressionAttributeNames={'#loc': 'location'},  # 'location' is a reserved word
            Limit=29  # Only 29 hospitals total
        )
        hospitals = response.get('Items', [])
        
        # Sort by affordability descending and limit to top 5
        hospitals.sort(key=lambda x: float(x.get('affordability', 0)), reverse=True)
        
        # Clean up response data and return top 5
        result = [clean_hospital_data(h) for h in hospitals[:5]]
        
        logger.info(f"get_hospitals_by_affordability execution time: {time.time() - start:.3f}s")
        return result
    except Exception as e:
        logger.error(f"get_hospitals_by_affordability execution time: {time.time() - start:.3f}s (failed)")
        raise Exception(f"Error fetching hospitals by affordability: {str(e)}")

def get_hospitals_by_insurance(insurance_company_id=None, insurance_name=None):
    """
    Returns hospitals that support a particular insurance company.
    Accepts either insurance_company_id OR insurance_name.
    If insurance_name is provided, automatically looks up the ID using GSI.
    
    Args:
        insurance_company_id: The ID of the insurance company (optional if insurance_name provided)
        insurance_name: The name of the insurance company (optional if insurance_company_id provided)
    
    Returns:
        List of hospitals that accept the specified insurance
    """
    start = time.time()
    try:
        # If insurance_name is provided, look up the ID using GSI query
        if insurance_name and not insurance_company_id:
            logger.info(f"Looking up insurance company ID for name: {insurance_name}")
            
            # Use GSI query (exact match)
            insurance_response = INSURANCE_COMPANY_TABLE.query(
                IndexName='insuranceCompanyName-index',
                KeyConditionExpression=Key('insuranceCompanyName').eq(insurance_name),
                ProjectionExpression='insuranceCompanyId',
                Limit=1
            )
            companies = insurance_response.get('Items', [])
            
            if not companies:
                logger.info(f"No insurance company found with name: {insurance_name}")
                logger.info(f"get_hospitals_by_insurance execution time: {time.time() - start:.3f}s")
                return []  # No matching insurance company found
            
            # Use the first match
            insurance_company_id = companies[0].get('insuranceCompanyId')
            logger.info(f"Found insurance company ID: {insurance_company_id}")
        
        if not insurance_company_id:
            raise ValueError("Either insurance_company_id or insurance_name must be provided")
        
        # Single scan with projection - Hospital table only has 29 rows
        response = HOSPITAL_TABLE.scan(
            ProjectionExpression='hospitalId, hospitalName, rating, affordability, avgCost, minCost, maxCost, insuranceCompanyIds, #loc, address',
            ExpressionAttributeNames={'#loc': 'location'},
            Limit=29
        )
        hospitals = response.get('Items', [])
        
        # Filter in memory (no additional DynamoDB calls)
        filtered_hospitals = []
        for hospital in hospitals:
            insurance_ids = hospital.get('insuranceCompanyIds', '[]')
            if isinstance(insurance_ids, str):
                insurance_ids = json.loads(insurance_ids)
            
            if insurance_company_id in insurance_ids:
                filtered_hospitals.append(clean_hospital_data(hospital))
        
        # Return top 5
        result = filtered_hospitals[:5]
        
        logger.info(f"get_hospitals_by_insurance execution time: {time.time() - start:.3f}s")
        return result
    except Exception as e:
        logger.error(f"get_hospitals_by_insurance execution time: {time.time() - start:.3f}s (failed)")
        raise Exception(f"Error fetching hospitals by insurance: {str(e)}")

def get_hospitals_with_high_insurance_coverage(min_approval_rate=0.8):
    """
    Returns hospitals with high insurance claim approval rates.
    
    Args:
        min_approval_rate: Minimum approval rate (0.0 to 1.0), default 0.8 (80%)
    
    Returns:
        List of hospitals with high insurance coverage approval rates
    """
    start = time.time()
    try:
        # Convert float to Decimal for DynamoDB
        min_approval_rate = float(min_approval_rate)
        
        response = HOSPITAL_TABLE.scan(
            ProjectionExpression='hospitalId, hospitalName, rating, affordability, avgCost, totalNumberOfClaims, totalNumberOfClaimsApproved, #loc, address',
            ExpressionAttributeNames={'#loc': 'location'},
            Limit=29  # Only 29 hospitals
        )
        hospitals = response.get('Items', [])
        
        # Filter hospitals with high approval rates
        filtered_hospitals = []
        for hospital in hospitals:
            total_claims = float(hospital.get('totalNumberOfClaims', 0))
            approved_claims = float(hospital.get('totalNumberOfClaimsApproved', 0))
            
            if total_claims > 0:
                approval_rate = approved_claims / total_claims
                if approval_rate >= min_approval_rate:
                    hospital['approvalRate'] = Decimal(str(approval_rate))
                    filtered_hospitals.append(clean_hospital_data(hospital))
        
        # Sort by approval rate descending and return top 5
        filtered_hospitals.sort(key=lambda x: float(x.get('approvalRate', 0)), reverse=True)
        result = filtered_hospitals[:5]
        
        logger.info(f"get_hospitals_with_high_insurance_coverage execution time: {time.time() - start:.3f}s")
        return result
    except Exception as e:
        logger.error(f"get_hospitals_with_high_insurance_coverage execution time: {time.time() - start:.3f}s (failed)")
        raise Exception(f"Error fetching hospitals with high insurance coverage: {str(e)}")

def get_hospitals_with_top_doctors_in_department(department_name, min_rating=3.5):
    """
    Returns hospitals with top-rated doctors in a particular department.
    OPTIMIZED: Uses GSI query + batch_get_item instead of scan + loops.
    
    Args:
        department_name: Name of the department (e.g., "Department of Cardiology")
        min_rating: Minimum doctor rating (0.0 to 5.0), default 3.5
                   Rating scale: 3.5-3.9 = Very Good, 4.0+ = Excellent
    
    Returns:
        List of hospitals with top doctors and their details in the specified department
    """
    start = time.time()
    try:
        # Convert float for comparison
        min_rating = float(min_rating)
        
        # Use GSI query
        dept_response = DEPARTMENT_TABLE.query(
            IndexName='departmentName-index',
            KeyConditionExpression=Key('departmentName').eq(department_name),
            ProjectionExpression='departmentId, hospitalId, listOfDoctorIds',
            Limit=50  # Limit departments to process
        )
        departments = dept_response.get('Items', [])
        
        if not departments:
            logger.info(f"get_hospitals_with_top_doctors_in_department execution time: {time.time() - start:.3f}s")
            return []
        
        # Collect all doctor IDs and hospital IDs
        all_doctor_ids = []
        hospital_ids = set()
        dept_to_hospital = {}
        
        for dept in departments:
            hospital_id = dept.get('hospitalId')
            doctor_ids = dept.get('listOfDoctorIds', '[]')
            if isinstance(doctor_ids, str):
                doctor_ids = json.loads(doctor_ids)
            
            all_doctor_ids.extend(doctor_ids)
            hospital_ids.add(hospital_id)
            dept_to_hospital[dept.get('departmentId')] = hospital_id
        
        # Remove duplicates
        all_doctor_ids = list(set(all_doctor_ids))
        
        # Use batch_get_item via resource API
        doctors = []
        if all_doctor_ids:
            # DynamoDB batch_get_item limit is 100 items per request
            for i in range(0, len(all_doctor_ids), 100):
                batch_doctor_ids = all_doctor_ids[i:i+100]
                
                # Use resource API batch_get_item
                response = dynamodb.batch_get_item(
                    RequestItems={
                        'Doctor': {
                            'Keys': [{'doctorId': doc_id} for doc_id in batch_doctor_ids],
                            'ProjectionExpression': 'doctorId, doctorName, rating, departmentId'
                        }
                    }
                )
                batch_doctors = response.get('Responses', {}).get('Doctor', [])
                doctors.extend(batch_doctors)
        
        # Filter doctors by rating and group by hospital
        hospital_data = {}
        for doctor in doctors:
            rating = float(doctor.get('rating', 0))
            
            if rating >= min_rating:
                # Get hospital ID from department
                dept_id = doctor.get('departmentId', '')
                hospital_id = dept_to_hospital.get(dept_id)
                
                if not hospital_id:
                    # Try to find hospital from departments
                    for dept in departments:
                        dept_doctor_ids = dept.get('listOfDoctorIds', '[]')
                        if isinstance(dept_doctor_ids, str):
                            dept_doctor_ids = json.loads(dept_doctor_ids)
                        doctor_id = doctor.get('doctorId', '')
                        if doctor_id in dept_doctor_ids:
                            hospital_id = dept.get('hospitalId')
                            break
                
                if hospital_id:
                    if hospital_id not in hospital_data:
                        hospital_data[hospital_id] = {'doctors': [], 'count': 0}
                    
                    # Create minimal doctor info
                    doctor_info = {
                        'doctorId': doctor.get('doctorId', ''),
                        'doctorName': doctor.get('doctorName', ''),
                        'rating': rating,
                        'specialization': department_name
                    }
                    hospital_data[hospital_id]['doctors'].append(doctor_info)
                    hospital_data[hospital_id]['count'] += 1
        
        if not hospital_data:
            logger.info(f"get_hospitals_with_top_doctors_in_department execution time: {time.time() - start:.3f}s")
            return []
        
        # Use batch_get_item for hospitals via resource API
        hospital_ids_list = list(hospital_data.keys())
        hospitals_dict = {}
        
        # Batch get hospitals (max 100 per request)
        for i in range(0, len(hospital_ids_list), 100):
            batch_hospital_ids = hospital_ids_list[i:i+100]
            
            response = dynamodb.batch_get_item(
                RequestItems={
                    'Hospital': {
                        'Keys': [{'hospitalId': hosp_id} for hosp_id in batch_hospital_ids],
                        'ProjectionExpression': 'hospitalId, hospitalName, rating, affordability, avgCost, minCost, maxCost, #loc, address',
                        'ExpressionAttributeNames': {'#loc': 'location'}
                    }
                }
            )
            batch_hospitals = response.get('Responses', {}).get('Hospital', [])
            for hosp in batch_hospitals:
                hosp_id = hosp.get('hospitalId', '')
                hospitals_dict[hosp_id] = hosp
        
        # Combine hospital and doctor data
        result_hospitals = []
        for hospital_id, data in hospital_data.items():
            hospital = hospitals_dict.get(hospital_id)
            if hospital:
                # Clean hospital data
                cleaned_hospital = clean_hospital_data(hospital)
                
                # Add doctor information
                cleaned_hospital['topDoctorsCount'] = data['count']
                cleaned_hospital['topDoctors'] = sorted(
                    data['doctors'], 
                    key=lambda x: float(x.get('rating', 0)), 
                    reverse=True
                )
                
                result_hospitals.append(cleaned_hospital)
        
        # Sort by top doctors count descending and return top 5
        result_hospitals.sort(key=lambda x: x.get('topDoctorsCount', 0), reverse=True)
        result = result_hospitals[:5]
        
        logger.info(f"get_hospitals_with_top_doctors_in_department execution time: {time.time() - start:.3f}s")
        return result
    except Exception as e:
        logger.error(f"get_hospitals_with_top_doctors_in_department execution time: {time.time() - start:.3f}s (failed)")
        raise Exception(f"Error fetching hospitals with top doctors: {str(e)}")

def get_hospitals_by_surgery_cost(min_cost=None, max_cost=None):
    """
    Returns hospitals where surgery costs are within a specified range.
    Uses minCost, maxCost, and avgCost fields when available.
    Falls back to affordability score when cost data is unavailable.
    
    Args:
        min_cost: Minimum cost threshold (optional)
        max_cost: Maximum cost threshold (optional)
    
    Returns:
        List of hospitals matching the cost criteria
    """
    start = time.time()
    try:
        # Convert to Decimal for DynamoDB comparison
        if min_cost is not None:
            min_cost = Decimal(str(min_cost))
        if max_cost is not None:
            max_cost = Decimal(str(max_cost))
        
        # Use ProjectionExpression to fetch only needed fields
        response = HOSPITAL_TABLE.scan(
            ProjectionExpression='hospitalId, hospitalName, avgCost, minCost, maxCost, affordability, rating, #loc, address',
            ExpressionAttributeNames={'#loc': 'location'},
            Limit=29  # Only 29 hospitals
        )
        hospitals = response.get('Items', [])
        
        filtered_hospitals = []
        hospitals_without_cost_data = []
        
        for hospital in hospitals:
            avg_cost = hospital.get('avgCost')
            min_hospital_cost = hospital.get('minCost')
            max_hospital_cost = hospital.get('maxCost')
            affordability = hospital.get('affordability')
            
            # Check if hospital has any cost data
            has_cost_data = avg_cost is not None or min_hospital_cost is not None or max_hospital_cost is not None
            
            if has_cost_data:
                # Use avgCost if available, otherwise use minCost, otherwise use maxCost
                cost_to_compare = avg_cost or min_hospital_cost or max_hospital_cost
                
                # Apply filters based on provided parameters
                matches = False
                if min_cost is not None and max_cost is not None:
                    # Between range - check if hospital's cost range overlaps with user's range
                    hospital_min = min_hospital_cost or cost_to_compare
                    hospital_max = max_hospital_cost or cost_to_compare
                    # Hospital matches if its range overlaps with user's range
                    if hospital_min <= max_cost and hospital_max >= min_cost:
                        matches = True
                elif min_cost is not None:
                    # Greater than or equal to min_cost
                    # Use minCost if available to be more inclusive
                    cost_check = min_hospital_cost or cost_to_compare
                    if cost_check >= min_cost or (max_hospital_cost and max_hospital_cost >= min_cost):
                        matches = True
                elif max_cost is not None:
                    # Less than or equal to max_cost
                    # Use minCost if available to be more inclusive (if min is under budget, hospital qualifies)
                    cost_check = min_hospital_cost or cost_to_compare
                    if cost_check <= max_cost:
                        matches = True
                else:
                    # No filter, return all with cost data
                    matches = True
                
                if matches:
                    cleaned = clean_hospital_data(hospital)
                    cleaned['costDataAvailable'] = True
                    filtered_hospitals.append(cleaned)
            else:
                # No cost data - use affordability as fallback
                if affordability is not None:
                    # If user wants low cost (max_cost specified), show high affordability hospitals
                    if max_cost is not None:
                        # Map max_cost to affordability threshold
                        # Lower max_cost = need higher affordability
                        # Rough mapping: 50000 -> 0.7, 100000 -> 0.6, 200000+ -> 0.5
                        max_cost_float = float(max_cost)
                        if max_cost_float <= 50000:
                            affordability_threshold = 0.7
                        elif max_cost_float <= 100000:
                            affordability_threshold = 0.6
                        elif max_cost_float <= 200000:
                            affordability_threshold = 0.5
                        else:
                            affordability_threshold = 0.4
                        
                        if float(affordability) >= affordability_threshold:
                            cleaned = clean_hospital_data(hospital)
                            cleaned['costDataAvailable'] = False
                            cleaned['estimatedAffordability'] = affordability
                            hospitals_without_cost_data.append(cleaned)
                    elif min_cost is None:
                        # No cost filter specified, include all
                        cleaned = clean_hospital_data(hospital)
                        cleaned['costDataAvailable'] = False
                        hospitals_without_cost_data.append(cleaned)
        
        # Combine results: hospitals with cost data first, then by affordability
        if filtered_hospitals:
            # Sort hospitals with cost data by average cost ascending
            filtered_hospitals.sort(key=lambda x: float(x.get('avgCost') or x.get('minCost') or x.get('maxCost') or float('inf')))
        
        if hospitals_without_cost_data:
            # Sort by affordability descending (higher affordability = lower cost)
            hospitals_without_cost_data.sort(key=lambda x: float(x.get('affordability', 0)), reverse=True)
        
        # Return top 5 results only
        all_results = filtered_hospitals + hospitals_without_cost_data
        result = all_results[:5]
        
        logger.info(f"get_hospitals_by_surgery_cost execution time: {time.time() - start:.3f}s")
        return result
    except Exception as e:
        logger.error(f"get_hospitals_by_surgery_cost execution time: {time.time() - start:.3f}s (failed)")
        raise Exception(f"Error fetching hospitals by surgery cost: {str(e)}")

def get_doctors_by_specialization(specialization):
    """
    Returns doctors specialized in a particular field/department.
    OPTIMIZED: Uses GSI query + batch_get_item instead of scan + loops.
    
    Args:
        specialization: Department name or specialization (e.g., "Department of Cardiology")
    
    Returns:
        List of doctors specialized in the specified field (top 5 by rating)
    """
    start = time.time()
    try:
        # Use GSI query
        dept_response = DEPARTMENT_TABLE.query(
            IndexName='departmentName-index',
            KeyConditionExpression=Key('departmentName').eq(specialization),
            ProjectionExpression='departmentId, hospitalId, listOfDoctorIds, departmentName',
            Limit=50  # Limit departments to process
        )
        departments = dept_response.get('Items', [])
        
        if not departments:
            logger.info(f"get_doctors_by_specialization execution time: {time.time() - start:.3f}s")
            return []
        
        # Collect all doctor IDs and hospital IDs
        all_doctor_ids = []
        hospital_ids = set()
        dept_to_hospital = {}
        
        for dept in departments:
            hospital_id = dept.get('hospitalId')
            doctor_ids = dept.get('listOfDoctorIds', '[]')
            if isinstance(doctor_ids, str):
                doctor_ids = json.loads(doctor_ids)
            
            all_doctor_ids.extend(doctor_ids)
            hospital_ids.add(hospital_id)
            dept_to_hospital[dept.get('departmentId')] = hospital_id
        
        # Remove duplicates
        all_doctor_ids = list(set(all_doctor_ids))
        
        # Use batch_get_item for doctors via resource API
        doctors = []
        if all_doctor_ids:
            # DynamoDB batch_get_item limit is 100 items per request
            for i in range(0, len(all_doctor_ids), 100):
                batch_doctor_ids = all_doctor_ids[i:i+100]
                
                response = dynamodb.batch_get_item(
                    RequestItems={
                        'Doctor': {
                            'Keys': [{'doctorId': doc_id} for doc_id in batch_doctor_ids],
                            'ProjectionExpression': 'doctorId, doctorName, rating, departmentId'
                        }
                    }
                )
                batch_doctors = response.get('Responses', {}).get('Doctor', [])
                doctors.extend(batch_doctors)
        
        # Use batch_get_item for hospitals via resource API
        hospital_ids_list = list(hospital_ids)
        hospitals_dict = {}
        
        if hospital_ids_list:
            # Batch get hospitals (max 100 per request)
            for i in range(0, len(hospital_ids_list), 100):
                batch_hospital_ids = hospital_ids_list[i:i+100]
                
                response = dynamodb.batch_get_item(
                    RequestItems={
                        'Hospital': {
                            'Keys': [{'hospitalId': hosp_id} for hosp_id in batch_hospital_ids],
                            'ProjectionExpression': 'hospitalId, hospitalName'
                        }
                    }
                )
                batch_hospitals = response.get('Responses', {}).get('Hospital', [])
                for hosp in batch_hospitals:
                    hosp_id = hosp.get('hospitalId', '')
                    hospitals_dict[hosp_id] = hosp
        
        # Build doctor list with hospital information
        all_doctors = []
        for doctor in doctors:
            doctor_id = doctor.get('doctorId', '')
            doctor_name = doctor.get('doctorName', '')
            rating = float(doctor.get('rating', 0))
            dept_id = doctor.get('departmentId', '')
            
            # Get hospital ID from department mapping
            hospital_id = dept_to_hospital.get(dept_id, 'Unknown')
            
            # Get hospital name from hospitals dict
            hospital = hospitals_dict.get(hospital_id, {})
            hospital_name = hospital.get('hospitalName', 'Unknown')
            
            # Create minimal doctor data
            doctor_minimal = {
                'doctorId': doctor_id,
                'doctorName': doctor_name,
                'rating': rating,
                'specialization': specialization,
                'hospitalName': hospital_name,
                'hospitalId': hospital_id
            }
            all_doctors.append(doctor_minimal)
        
        # Sort by rating descending and return top 5
        all_doctors.sort(key=lambda x: float(x.get('rating', 0)), reverse=True)
        result = all_doctors[:5]
        
        logger.info(f"get_doctors_by_specialization execution time: {time.time() - start:.3f}s")
        return result
    except Exception as e:
        logger.error(f"get_doctors_by_specialization execution time: {time.time() - start:.3f}s (failed)")
        raise Exception(f"Error fetching doctors by specialization: {str(e)}")

def get_hospital_id_by_name(hospital_name):
    """
    Returns hospitalId given a hospital name.
    Uses case-insensitive partial matching to find hospitals.
    
    Args:
        hospital_name: Name of the hospital (partial match supported)
    
    Returns:
        List of matching hospitals with hospitalId and hospitalName
    """
    start = time.time()
    try:
        # Scan hospitals with projection (only 29 hospitals)
        response = HOSPITAL_TABLE.scan(
            ProjectionExpression='hospitalId, hospitalName',
            Limit=29
        )
        hospitals = response.get('Items', [])
        
        # Filter by name (case-insensitive partial match)
        hospital_name_lower = hospital_name.lower()
        matching_hospitals = []
        
        for hospital in hospitals:
            hosp_name = hospital.get('hospitalName', '')
            if hospital_name_lower in hosp_name.lower():
                matching_hospitals.append({
                    'hospitalId': hospital.get('hospitalId'),
                    'hospitalName': hosp_name
                })
        
        # Sort by name and return top 5
        matching_hospitals.sort(key=lambda x: x.get('hospitalName', ''))
        result = matching_hospitals[:5]
        
        logger.info(f"get_hospital_id_by_name execution time: {time.time() - start:.3f}s")
        return result
    except Exception as e:
        logger.error(f"get_hospital_id_by_name execution time: {time.time() - start:.3f}s (failed)")
        raise Exception(f"Error fetching hospital ID by name: {str(e)}")

def get_doctor_id_by_name(doctor_name=None, doctor_id=None):
    """
    Returns doctorId and complete details given doctor name and/or doctorId.
    Accepts either doctor_name OR doctor_id (or both for validation).
    This is the unified function for all doctor lookups.
    
    Args:
        doctor_name: Name of the doctor (partial match supported, optional)
        doctor_id: ID of the doctor (exact match, optional)
    
    Returns:
        List of matching doctors with complete details including doctorId, doctorName, rating, 
        specialization, yearsOfExperience, hospitalName, and hospitalId
    """
    start = time.time()
    try:
        if not doctor_name and not doctor_id:
            raise ValueError("Either doctor_name or doctor_id must be provided")
        
        # If doctor_id is provided, get that specific doctor
        if doctor_id:
            try:
                doctor_response = DOCTOR_TABLE.get_item(
                    Key={'doctorId': doctor_id},
                    ProjectionExpression='doctorId, doctorName, rating, departmentId, specialty, yearsOfExperience'
                )
                doctor = doctor_response.get('Item')
                
                if doctor:
                    # Get department and hospital info
                    dept_id = doctor.get('departmentId', '')
                    hospital_name = 'Unknown'
                    hospital_id = 'Unknown'
                    specialization = doctor.get('specialty', 'General')
                    
                    if dept_id:
                        try:
                            dept_response = DEPARTMENT_TABLE.get_item(
                                Key={'departmentId': dept_id},
                                ProjectionExpression='hospitalId, departmentName'
                            )
                            dept = dept_response.get('Item', {})
                            hospital_id = dept.get('hospitalId', 'Unknown')
                            
                            # Use department name as specialization if specialty field is empty
                            if not specialization or specialization == 'General':
                                specialization = dept.get('departmentName', 'General')
                            
                            # Get hospital name
                            if hospital_id != 'Unknown':
                                hosp_response = HOSPITAL_TABLE.get_item(
                                    Key={'hospitalId': hospital_id},
                                    ProjectionExpression='hospitalName'
                                )
                                hosp = hosp_response.get('Item', {})
                                hospital_name = hosp.get('hospitalName', 'Unknown')
                        except Exception as e:
                            logger.error(f"Error fetching department/hospital: {str(e)}")
                    
                    result = [{
                        'doctorId': doctor.get('doctorId'),
                        'doctorName': doctor.get('doctorName'),
                        'rating': float(doctor.get('rating', 0)),
                        'specialization': specialization,
                        'yearsOfExperience': int(doctor.get('yearsOfExperience', 0)) if doctor.get('yearsOfExperience') else None,
                        'hospitalName': hospital_name,
                        'hospitalId': hospital_id
                    }]
                    
                    logger.info(f"get_doctor_id_by_name execution time: {time.time() - start:.3f}s")
                    return result
                else:
                    logger.info(f"get_doctor_id_by_name execution time: {time.time() - start:.3f}s")
                    return []
            except Exception as e:
                logger.error(f"Error fetching doctor by ID: {str(e)}")
                # Fall through to name search if ID lookup fails
        
        # If doctor_name is provided, search by name
        if doctor_name:
            # Scan doctors (976 doctors - need to scan)
            response = DOCTOR_TABLE.scan(
                ProjectionExpression='doctorId, doctorName, rating, departmentId, specialty, yearsOfExperience',
                Limit=1000  # Limit to prevent excessive scanning
            )
            doctors = response.get('Items', [])
            
            # Filter by name (case-insensitive partial match)
            doctor_name_lower = doctor_name.lower()
            matching_doctors = []
            
            for doctor in doctors:
                doc_name = doctor.get('doctorName', '')
                if doctor_name_lower in doc_name.lower():
                    matching_doctors.append(doctor)
            
            # Get hospital information for matching doctors
            result_doctors = []
            for doctor in matching_doctors[:10]:  # Limit to 10 for batch processing
                dept_id = doctor.get('departmentId', '')
                specialization = doctor.get('specialty', 'General')
                
                try:
                    # Get department to find hospital
                    dept_response = DEPARTMENT_TABLE.get_item(
                        Key={'departmentId': dept_id},
                        ProjectionExpression='hospitalId, departmentName'
                    )
                    dept = dept_response.get('Item', {})
                    hospital_id = dept.get('hospitalId', 'Unknown')
                    
                    # Use department name as specialization if specialty field is empty
                    if not specialization or specialization == 'General':
                        specialization = dept.get('departmentName', 'General')
                    
                    # Get hospital name
                    if hospital_id != 'Unknown':
                        hosp_response = HOSPITAL_TABLE.get_item(
                            Key={'hospitalId': hospital_id},
                            ProjectionExpression='hospitalName'
                        )
                        hosp = hosp_response.get('Item', {})
                        hospital_name = hosp.get('hospitalName', 'Unknown')
                    else:
                        hospital_name = 'Unknown'
                    
                    result_doctors.append({
                        'doctorId': doctor.get('doctorId'),
                        'doctorName': doctor.get('doctorName'),
                        'rating': float(doctor.get('rating', 0)),
                        'specialization': specialization,
                        'yearsOfExperience': int(doctor.get('yearsOfExperience', 0)) if doctor.get('yearsOfExperience') else None,
                        'hospitalName': hospital_name,
                        'hospitalId': hospital_id
                    })
                except:
                    continue
            
            # Sort by rating descending and return top 5
            result_doctors.sort(key=lambda x: x.get('rating', 0), reverse=True)
            result = result_doctors[:5]
            
            logger.info(f"get_doctor_id_by_name execution time: {time.time() - start:.3f}s")
            return result
        
        logger.info(f"get_doctor_id_by_name execution time: {time.time() - start:.3f}s")
        return []
    except Exception as e:
        logger.error(f"get_doctor_id_by_name execution time: {time.time() - start:.3f}s (failed)")
        raise Exception(f"Error fetching doctor ID by name: {str(e)}")


def get_hospital_doctors(hospital_id, department_name=None):
    """
    Get doctors for a specific hospital, optionally filtered by department.
    
    Args:
        hospital_id: The unique identifier for the hospital
        department_name: Optional department name (e.g., "Department of Cardiology")
                        If not provided, returns top doctors across all departments
    
    Returns:
        List of up to 5 doctors sorted by rating descending
    """
    start = time.time()
    try:
        if not hospital_id:
            raise ValueError("hospital_id is required")
        
        # Get hospital to verify it exists and get name
        hospital_response = HOSPITAL_TABLE.get_item(
            Key={'hospitalId': hospital_id},
            ProjectionExpression='hospitalName, departmentIds'
        )
        hospital = hospital_response.get('Item')
        
        if not hospital:
            logger.info(f"Hospital not found: {hospital_id}")
            logger.info(f"get_hospital_doctors execution time: {time.time() - start:.3f}s")
            return []
        
        hospital_name = hospital.get('hospitalName', 'Unknown')
        
        # If department_name is provided, filter by that department
        if department_name:
            # Query departments by name using GSI, then filter by hospitalId
            dept_response = DEPARTMENT_TABLE.query(
                IndexName='departmentName-index',
                KeyConditionExpression=Key('departmentName').eq(department_name),
                ProjectionExpression='departmentId, hospitalId, listOfDoctorIds',
                Limit=50
            )
            departments = dept_response.get('Items', [])
            
            # Filter to only this hospital's department
            hospital_dept = None
            for dept in departments:
                if dept.get('hospitalId') == hospital_id:
                    hospital_dept = dept
                    break
            
            if not hospital_dept:
                logger.info(f"Department {department_name} not found in hospital {hospital_id}")
                logger.info(f"get_hospital_doctors execution time: {time.time() - start:.3f}s")
                return []
            
            # Get doctor IDs from department
            doctor_ids = hospital_dept.get('listOfDoctorIds', '[]')
            if isinstance(doctor_ids, str):
                doctor_ids = json.loads(doctor_ids)
            
            if not doctor_ids:
                logger.info(f"No doctors found in department {department_name} at hospital {hospital_id}")
                logger.info(f"get_hospital_doctors execution time: {time.time() - start:.3f}s")
                return []
            
            # Use batch_get_item for doctors
            doctors = []
            for i in range(0, len(doctor_ids), 100):
                batch_doctor_ids = doctor_ids[i:i+100]
                
                response = dynamodb.batch_get_item(
                    RequestItems={
                        'Doctor': {
                            'Keys': [{'doctorId': doc_id} for doc_id in batch_doctor_ids],
                            'ProjectionExpression': 'doctorId, doctorName, rating'
                        }
                    }
                )
                batch_doctors = response.get('Responses', {}).get('Doctor', [])
                doctors.extend(batch_doctors)
            
            # Build result with doctor details
            result_doctors = []
            for doctor in doctors:
                result_doctors.append({
                    'doctorId': doctor.get('doctorId'),
                    'doctorName': doctor.get('doctorName'),
                    'rating': float(doctor.get('rating', 0)),
                    'specialization': department_name,
                    'hospitalName': hospital_name,
                    'hospitalId': hospital_id
                })
        else:
            # No department specified - get all doctors from all departments
            department_ids = hospital.get('departmentIds', '[]')
            if isinstance(department_ids, str):
                department_ids = json.loads(department_ids)
            
            if not department_ids:
                logger.info(f"No departments found for hospital: {hospital_id}")
                logger.info(f"get_hospital_doctors execution time: {time.time() - start:.3f}s")
                return []
            
            # Get all doctors from all departments
            all_doctor_ids = []
            for dept_id in department_ids:
                try:
                    dept_response = DEPARTMENT_TABLE.get_item(
                        Key={'departmentId': dept_id},
                        ProjectionExpression='listOfDoctorIds, departmentName'
                    )
                    dept = dept_response.get('Item', {})
                    doctor_ids = dept.get('listOfDoctorIds', '[]')
                    if isinstance(doctor_ids, str):
                        doctor_ids = json.loads(doctor_ids)
                    all_doctor_ids.extend(doctor_ids)
                except:
                    continue
            
            # Remove duplicates
            all_doctor_ids = list(set(all_doctor_ids))
            
            if not all_doctor_ids:
                logger.info(f"No doctors found for hospital: {hospital_id}")
                logger.info(f"get_hospital_doctors execution time: {time.time() - start:.3f}s")
                return []
            
            # Use batch_get_item for doctors
            doctors = []
            for i in range(0, len(all_doctor_ids), 100):
                batch_doctor_ids = all_doctor_ids[i:i+100]
                
                response = dynamodb.batch_get_item(
                    RequestItems={
                        'Doctor': {
                            'Keys': [{'doctorId': doc_id} for doc_id in batch_doctor_ids],
                            'ProjectionExpression': 'doctorId, doctorName, rating, departmentId'
                        }
                    }
                )
                batch_doctors = response.get('Responses', {}).get('Doctor', [])
                doctors.extend(batch_doctors)
            
            # Get department names for doctors
            dept_names = {}
            for doctor in doctors:
                dept_id = doctor.get('departmentId', '')
                if dept_id and dept_id not in dept_names:
                    try:
                        dept_response = DEPARTMENT_TABLE.get_item(
                            Key={'departmentId': dept_id},
                            ProjectionExpression='departmentName'
                        )
                        dept = dept_response.get('Item', {})
                        dept_names[dept_id] = dept.get('departmentName', 'General')
                    except:
                        dept_names[dept_id] = 'General'
            
            # Build result with doctor details
            result_doctors = []
            for doctor in doctors:
                dept_id = doctor.get('departmentId', '')
                specialization = dept_names.get(dept_id, 'General')
                
                result_doctors.append({
                    'doctorId': doctor.get('doctorId'),
                    'doctorName': doctor.get('doctorName'),
                    'rating': float(doctor.get('rating', 0)),
                    'specialization': specialization,
                    'hospitalName': hospital_name,
                    'hospitalId': hospital_id
                })
        
        # Sort by rating descending and return top 5
        result_doctors.sort(key=lambda x: x.get('rating', 0), reverse=True)
        result = result_doctors[:5]
        
        logger.info(f"get_hospital_doctors execution time: {time.time() - start:.3f}s")
        return result
    except Exception as e:
        logger.error(f"get_hospital_doctors execution time: {time.time() - start:.3f}s (failed)")
        raise Exception(f"Error fetching doctors for hospital: {str(e)}")

def lambda_handler(event, context):
    """
    Main Lambda handler function for hospital and doctor search operations.
    
    Supported operations:
    - get_all_insurance_companies
    - get_hospitals_by_affordability
    - get_hospitals_by_insurance
    - get_hospitals_with_high_insurance_coverage (alias: get_hospitals_high_insurance_coverage)
    - get_hospitals_with_top_doctors_in_department (alias: get_hospitals_top_doctors_in_dept)
    - get_hospitals_by_surgery_cost
    - get_doctors_by_specialization
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Parse the request - Bedrock sends different format than direct invocation
        # Bedrock format: event has 'actionGroup', 'function', 'parameters'
        # Direct format: event has 'operation', 'parameters'
        
        if 'function' in event:
            # Bedrock agent format
            operation = event.get('function')
            parameters = event.get('parameters', [])
            
            # Convert parameters from Bedrock format (list of dicts) to simple dict
            if isinstance(parameters, list):
                params_dict = {}
                for param in parameters:
                    if 'name' in param and 'value' in param:
                        params_dict[param['name']] = param['value']
                parameters = params_dict
        else:
            # Direct invocation format
            operation = event.get('operation')
            parameters = event.get('parameters', {})
        
        logger.info(f"Operation: {operation}, Parameters: {parameters}")
        
        # Store original operation name for response
        original_operation = operation
        
        # Strip action group prefix if present (e.g., "health_search__get_hospitals_by_affordability")
        if operation and '__' in operation:
            logger.info(f"Stripping action group prefix from operation: {operation}")
            operation = operation.split('__', 1)[1]
            logger.info(f"Operation after stripping prefix: {operation}")
        
        # Handle shortened operation names (aliases for Bedrock 64-char limit)
        operation_aliases = {
            'get_hospitals_high_insurance_coverage': 'get_hospitals_with_high_insurance_coverage',
            'get_hospitals_top_doctors_in_dept': 'get_hospitals_with_top_doctors_in_department'
        }
        operation = operation_aliases.get(operation, operation)
        
        # Route to appropriate function
        if operation == 'get_all_insurance_companies':
            result = get_all_insurance_companies()
        
        elif operation == 'get_hospitals_by_affordability':
            min_affordability = parameters.get('min_affordability', 0.0)
            max_affordability = parameters.get('max_affordability', 1.0)
            result = get_hospitals_by_affordability(min_affordability, max_affordability)
        
        elif operation == 'get_hospitals_by_insurance_name':
            # New function that accepts insurance name directly
            insurance_name = parameters.get('insurance_name')
            if not insurance_name:
                raise ValueError("insurance_name is required")
            result = get_hospitals_by_insurance(None, insurance_name)
        
        elif operation == 'get_hospitals_by_insurance':
            insurance_company_id = parameters.get('insurance_company_id')
            insurance_name = parameters.get('insurance_name')
            if not insurance_company_id and not insurance_name:
                raise ValueError("Either insurance_company_id or insurance_name is required")
            result = get_hospitals_by_insurance(insurance_company_id, insurance_name)
        
        elif operation == 'get_hospitals_with_high_insurance_coverage':
            min_approval_rate = parameters.get('min_approval_rate', 0.8)
            result = get_hospitals_with_high_insurance_coverage(min_approval_rate)
        
        elif operation == 'get_hospitals_with_top_doctors_in_department':
            department_name = parameters.get('department_name')
            if not department_name:
                raise ValueError("department_name is required")
            min_rating = parameters.get('min_rating', 3.5)
            result = get_hospitals_with_top_doctors_in_department(department_name, min_rating)
        
        elif operation == 'get_hospitals_by_surgery_cost':
            min_cost = parameters.get('min_cost')
            max_cost = parameters.get('max_cost')
            result = get_hospitals_by_surgery_cost(min_cost, max_cost)
        
        elif operation == 'get_doctors_by_specialization':
            specialization = parameters.get('specialization')
            if not specialization:
                raise ValueError("specialization is required")
            result = get_doctors_by_specialization(specialization)
        
        elif operation == 'get_hospital_id_by_name':
            hospital_name = parameters.get('hospital_name')
            if not hospital_name:
                raise ValueError("hospital_name is required")
            result = get_hospital_id_by_name(hospital_name)
        
        elif operation == 'get_doctor_id_by_name':
            doctor_name = parameters.get('doctor_name')
            doctor_id = parameters.get('doctor_id')
            if not doctor_name and not doctor_id:
                raise ValueError("Either doctor_name or doctor_id is required")
            result = get_doctor_id_by_name(doctor_name, doctor_id)
        
        elif operation == 'get_hospital_doctors':
            hospital_id = parameters.get('hospital_id') or parameters.get('hospitalId')
            department_name = parameters.get('department_name')
            if not hospital_id:
                raise ValueError("hospital_id is required")
            result = get_hospital_doctors(hospital_id, department_name)
        
        else:
            raise ValueError(f"Unknown operation: {operation}")
        
        # Return response in Bedrock-compatible format
        # For Bedrock agents, return the data directly without statusCode wrapper
        # IMPORTANT: Must return the ORIGINAL function name from the request, not the aliased version
        return {
            'response': {
                'actionGroup': event.get('actionGroup', 'health_search'),
                'function': original_operation,  # Use original operation name, not aliased
                'functionResponse': {
                    'responseBody': {
                        'TEXT': {
                            'body': json.dumps({
                                'success': True,
                                'data': result,
                                'count': len(result)
                            }, cls=DecimalEncoder)
                        }
                    }
                }
            }
        }
    
    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}")
        return {
            'response': {
                'actionGroup': event.get('actionGroup', 'health_search'),
                'function': event.get('function', 'unknown'),
                'functionResponse': {
                    'responseBody': {
                        'TEXT': {
                            'body': json.dumps({
                                'success': False,
                                'error': str(ve)
                            })
                        }
                    }
                }
            }
        }
    
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return {
            'response': {
                'actionGroup': event.get('actionGroup', 'health_search'),
                'function': event.get('function', 'unknown'),
                'functionResponse': {
                    'responseBody': {
                        'TEXT': {
                            'body': json.dumps({
                                'success': False,
                                'error': str(e)
                            })
                        }
                    }
                }
            }
        }
            
