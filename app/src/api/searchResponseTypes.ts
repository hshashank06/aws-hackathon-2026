/**
 * TypeScript types for AI-Powered Search Response
 * Use these interfaces for type-safe frontend development
 */

// ========================================================================
// REQUEST TYPES
// ========================================================================

export interface SearchRequest {
  query: string;
  userContext?: {
    insuranceId?: string;
    location?: {
      latitude: number;
      longitude: number;
    };
  };
}

// ========================================================================
// RESPONSE TYPES
// ========================================================================

export interface SearchResponse {
  success: boolean;
  cached: boolean;
  responseTime: string;
  fallback?: boolean;
  message?: string;
  userIntent: UserIntent;
  results: SearchResults;
  metadata: SearchMetadata;
}

export interface UserIntent {
  category: string;
  keywords: string[];
  insuranceRequired?: boolean;
  procedureType?: string;
}

export interface SearchResults {
  totalMatches: number;
  hospitals: EnrichedHospital[];
  aiSummary?: string;
}

// ========================================================================
// HOSPITAL TYPES
// ========================================================================

export interface EnrichedHospital {
  // Basic Info
  hospitalId: string;
  hospitalName: string;
  services: string[];
  location: HospitalLocation;
  address: string;
  phoneNumber: string;
  description: string;
  
  // AI Insights
  aiInsights: AIInsights | null;
  
  // Statistics
  stats: HospitalStats;
  
  // Insurance
  insuranceInfo: InsuranceInfo;
  
  // Departments
  relevantDepartments: Department[];
  
  // Doctors (key feature!)
  topDoctors: EnrichedDoctor[];
  
  // Costs
  costEstimates: CostEstimates;
  
  // Trust
  trustIndicators: TrustIndicators;
  
  // Facilities
  facilities: string[];
  
  // Images
  images: HospitalImage[];
}

export interface HospitalLocation {
  latitude: number;
  longitude: number;
  distance?: number; // km from user
}

// Additional fields for UI compatibility
export interface EnrichedHospitalExtended extends EnrichedHospital {
  coordinates?: { latitude: number; longitude: number };
  distance?: number;
}

export interface AIInsights {
  matchScore: number; // 0-100
  explanation: string;
  keyStrengths: string[];
  considerations: string[];
}

export interface HospitalStats {
  totalReviews: number;
  verifiedReviews: number;
  averageRating: number;
  ratingBreakdown: {
    serviceQuality: number;
    maintenance: number;
    foodQuality: number;
    cleanliness: number;
    staffBehavior: number;
  };
  claimApprovalRate: number; // 0.0-1.0
  averageCost: number; // in INR
  averageWaitTime: number; // in days
}

export interface InsuranceInfo {
  acceptedCompanies: InsuranceCompany[];
  userInsuranceMatch?: UserInsuranceMatch;
}

export interface InsuranceCompany {
  insuranceCompanyId: string;
  insuranceCompanyName: string;
  claimApprovalRate: number;
  averageClaimAmount: number;
  cashlessAvailable: boolean;
}

export interface UserInsuranceMatch {
  isAccepted: boolean;
  insuranceCompanyId: string;
  claimApprovalRate: number;
  estimatedCoverage: number;
  estimatedOutOfPocket: number;
}

export interface Department {
  departmentId: string;
  departmentName: string;
  departmentDescription: string;
  doctorCount: number;
  patientCount: number;
}

export interface CostEstimates {
  [procedureName: string]: ProcedureCost;
}

export interface ProcedureCost {
  minCost: number;
  maxCost: number;
  averageCost: number;
  currency: string;
  estimatedInsuranceCoverage: number;
  estimatedOutOfPocket: number;
  breakdown?: {
    [costType: string]: number;
  };
}

export interface TrustIndicators {
  verified: boolean;
  trustScore: number; // 0-100
  verificationBadge: 'bronze' | 'silver' | 'gold' | 'platinum';
  accreditations: string[];
  documentVerificationRate: number; // 0.0-1.0
  fakeReviewsBlocked: number;
}

export interface HospitalImage {
  url: string;
  type: 'exterior' | 'interior' | 'facility' | 'other';
  caption: string;
}

// ========================================================================
// DOCTOR TYPES
// ========================================================================

export interface EnrichedDoctor {
  // Basic Info
  doctorId: string;
  doctorName: string;
  specialty: string;
  experience: string;
  about: string;
  
  // AI Review (key feature!)
  aiReview: DoctorAIReview | null;
  
  // Statistics
  stats: DoctorStats;
  
  // Recent Reviews
  recentReviews: DoctorReview[];
  
  // Availability
  availability: DoctorAvailability;
}

export interface DoctorAIReview {
  summary: string;
  keyHighlights: string[];
}

export interface DoctorStats {
  totalReviews: number;
  verifiedReviews: number;
  averageRating: number;
  ratingBreakdown: {
    bedsideManner: number;
    medicalExpertise: number;
    communication: number;
    waitTime: number;
    thoroughness: number;
    followUpCare: number;
  };
  successRate: number; // 0.0-1.0
  totalSurgeries?: number;
  totalProcedures?: number;
}

export interface DoctorReview {
  reviewId: string;
  customerName: string;
  rating: number;
  procedureType: string;
  reviewText: string;
  verified: boolean;
  createdAt: string;
}

export interface DoctorAvailability {
  nextAvailableSlot: string; // ISO date
  averageWaitTime: number; // in days
  acceptingNewPatients: boolean;
}

// ========================================================================
// METADATA TYPES
// ========================================================================

export interface SearchMetadata {
  searchId: string;
  timestamp: string;
  aiModel: string | null;
  databaseVersion?: string;
  totalHospitalsInDatabase?: number;
  totalDoctorsInDatabase?: number;
  fallbackReason?: string;
}

// ========================================================================
// ERROR TYPES
// ========================================================================

export interface SearchErrorResponse {
  success: false;
  error: string;
  message: string;
  details?: {
    code: string;
    suggestion?: string;
  };
}

// ========================================================================
// HELPER TYPES
// ========================================================================

export type SearchResponseOrError = SearchResponse | SearchErrorResponse;

// Type guard
export function isSearchSuccess(response: SearchResponseOrError): response is SearchResponse {
  return response.success === true;
}

export function isSearchError(response: SearchResponseOrError): response is SearchErrorResponse {
  return response.success === false;
}
