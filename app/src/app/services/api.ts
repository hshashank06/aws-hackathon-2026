import { Hospital, mockHospitals, Doctor } from "../data/mockData";
import type { SearchResponse, EnrichedHospital, EnrichedDoctor } from "../../api/searchResponseTypes";

// API Configuration
const API_BASE_URL = "https://ri8zkgmzlb.execute-api.us-east-1.amazonaws.com";
const SEARCH_ENDPOINT = `${API_BASE_URL}/search`;

// Feature flag to toggle between real API and mock data
const USE_REAL_API = true; // Set to false to use mock data

// Simulates API delay
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Adapter: Convert backend hospital response to Hospital for UI
 * Includes null/undefined checks to prevent NPEs
 */
function adaptEnrichedHospitalToHospital(enriched: any): Hospital {
  // Validate input
  if (!enriched || typeof enriched !== 'object') {
    console.warn('[API] Invalid hospital data:', enriched);
    throw new Error('Invalid hospital data');
  }

  // Backend returns a simpler format
  return {
    id: enriched.id || '',
    name: enriched.name || 'Unknown Hospital',
    location: enriched.location || 'Unknown Location',
    rating: typeof enriched.rating === 'number' ? enriched.rating : 4.0,
    reviewCount: typeof enriched.reviewCount === 'number' ? enriched.reviewCount : 0,
    imageUrl: enriched.imageUrl || "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=400",
    description: enriched.description || "",
    specialties: Array.isArray(enriched.specialties) ? enriched.specialties : [],
    acceptedInsurance: Array.isArray(enriched.acceptedInsurance) 
      ? enriched.acceptedInsurance 
      : ["Blue Cross", "United Health", "Aetna", "Medicare"],
    avgCostRange: enriched.avgCostRange && typeof enriched.avgCostRange === 'object'
      ? {
          min: typeof enriched.avgCostRange.min === 'number' ? enriched.avgCostRange.min : 0,
          max: typeof enriched.avgCostRange.max === 'number' ? enriched.avgCostRange.max : 0,
        }
      : { min: 0, max: 0 },
    aiRecommendation: enriched.aiRecommendation || "",
    doctors: Array.isArray(enriched.doctors) ? enriched.doctors : [],
    reviews: Array.isArray(enriched.reviews) ? enriched.reviews : [],
    trustScore: typeof enriched.trustScore === 'number' ? enriched.trustScore : 85,
    verificationBadge: enriched.verificationBadge || "gold",
    insuranceCoveragePercent: typeof enriched.insuranceCoveragePercent === 'number' 
      ? enriched.insuranceCoveragePercent 
      : 0,
    topDoctorIds: Array.isArray(enriched.topDoctorIds) ? enriched.topDoctorIds : [],
    doctorAIReviews: enriched.doctorAIReviews || {},
  };
}

/**
 * Adapter: Convert backend doctor response to Doctor for UI
 */
function adaptEnrichedDoctorToDoctor(enriched: any): Doctor {
  return {
    id: enriched.id,
    name: enriched.name,
    specialty: enriched.specialty,
    experience: enriched.experience || 10,
    qualifications: enriched.qualifications || [],
    rating: enriched.rating || 4.0,
    reviewCount: enriched.reviewCount || 0,
    imageUrl: enriched.imageUrl || "https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=200",
    aiSummary: enriched.aiSummary || "",
    reviews: enriched.reviews || [],
  };
}

/**
 * Call the real Lambda search endpoint (async flow)
 * Step 1: Initiate search and get searchId
 */
async function initiateSearch(query: string, customerId?: string): Promise<{ searchId: string; status: string }> {
  // If query doesn't mention a location, append "in Hyderabad" as default
  let enhancedQuery = query;
  const hasLocation = /\b(in|near|at|around)\s+\w+/i.test(query) || 
                      /hyderabad|bangalore|mumbai|delhi|chennai|kolkata/i.test(query);
  
  if (!hasLocation) {
    enhancedQuery = `${query} in Hyderabad`;
    console.log(`[API] No location detected, enhanced query: "${enhancedQuery}"`);
  }

  const requestBody = {
    query: enhancedQuery,
    customerId: customerId || "anonymous",
    userContext: {},
  };

  console.log(`[API] Initiating search: ${SEARCH_ENDPOINT}`);
  console.log(`[API] Request:`, requestBody);

  const response = await fetch(SEARCH_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  const data = await response.json();
  console.log(`[API] Search initiated:`, data);

  return data;
}

/**
 * Poll for search results
 * Step 2: Poll until status is "complete" or "error"
 */
async function pollSearchStatus(searchId: string, maxAttempts: number = 30): Promise<SearchResponse> {
  const pollInterval = 5000; // 5 seconds
  
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    console.log(`[API] Polling search status (attempt ${attempt}/${maxAttempts}): ${searchId}`);
    
    const response = await fetch(`${SEARCH_ENDPOINT}/${searchId}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`Poll request failed: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    console.log(`[API] Poll response:`, data);

    if (data.status === "complete") {
      console.log(`[API] Search complete!`);
      
      // Validate response structure
      if (!data.results || !data.results.hospitals) {
        console.error(`[API] Invalid response structure:`, data);
        throw new Error("Invalid search response format");
      }
      
      return {
        success: true,
        results: {
          aiSummary: data.results.aiSummary || "",
          hospitals: data.results.hospitals || [],
          totalMatches: (data.results.hospitals || []).length,
        },
      };
    }

    if (data.status === "error") {
      console.error(`[API] Search failed:`, data.error);
      throw new Error(data.error || "Search processing failed");
    }

    // Status is still "processing", wait and retry
    if (attempt < maxAttempts) {
      console.log(`[API] Status: processing, waiting ${pollInterval}ms...`);
      await delay(pollInterval);
    }
  }

  throw new Error("Search timeout: Results not ready after maximum polling attempts");
}

/**
 * Call the real Lambda search endpoint (combines initiate + poll)
 */
async function callSearchAPI(query: string, customerId?: string): Promise<SearchResponse> {
  // Step 1: Initiate search
  const { searchId, status } = await initiateSearch(query, customerId);
  
  if (status === "error") {
    throw new Error("Failed to initiate search");
  }

  // Step 2: Poll for results
  return await pollSearchStatus(searchId);
}

/**
 * Search hospitals using real API or mock data
 * Returns both hospitals and searchId for lazy loading doctors
 */
export async function searchHospitalsAPI(query: string, customerId?: string): Promise<{ hospitals: Hospital[]; searchId: string | null }> {
  if (!query.trim()) {
    return { hospitals: [], searchId: null };
  }

  // Use real API if enabled
  if (USE_REAL_API) {
    try {
      console.log(`[API] Starting async search for: "${query}"`);
      
      // Step 1: Initiate search and capture searchId
      const { searchId, status } = await initiateSearch(query, customerId);
      
      if (status === "error") {
        throw new Error("Failed to initiate search");
      }

      // Step 2: Poll for results
      const response = await pollSearchStatus(searchId);

      console.log(`[API] Search completed successfully`);
      console.log(`[API] AI Summary:`, response.results.aiSummary);
      console.log(`[API] Found ${response.results.hospitals.length} hospitals`);

      // Convert backend hospital format to UI Hospital format
      // Filter out any invalid hospitals
      const hospitals = response.results.hospitals
        .map((h: any) => {
          try {
            return adaptEnrichedHospitalToHospital(h);
          } catch (error) {
            console.error('[API] Failed to adapt hospital:', error, h);
            return null;
          }
        })
        .filter((h: Hospital | null): h is Hospital => h !== null);

      return { hospitals, searchId };
    } catch (error) {
      console.error("[API] Error during search:", error);
      console.log("[API] Falling back to mock data");
      // Fall back to mock data on error
      return { hospitals: searchMockHospitals(query), searchId: null };
    }
  }

  // Use mock data
  return { hospitals: searchMockHospitals(query), searchId: null };
}

/**
 * Mock search implementation (fallback)
 */
function searchMockHospitals(query: string): Hospital[] {
  const lowerQuery = query.toLowerCase();

  const results = mockHospitals.filter((hospital) => {
    return (
      hospital.name.toLowerCase().includes(lowerQuery) ||
      hospital.description.toLowerCase().includes(lowerQuery) ||
      hospital.specialties.some((s) => s.toLowerCase().includes(lowerQuery)) ||
      hospital.location.toLowerCase().includes(lowerQuery) ||
      hospital.aiRecommendation.toLowerCase().includes(lowerQuery) ||
      hospital.doctors.some(
        (doctor) =>
          doctor.name.toLowerCase().includes(lowerQuery) ||
          doctor.specialty.toLowerCase().includes(lowerQuery)
      )
    );
  });

  console.log(`[API] Mock search for: "${query}"`);
  console.log(`[API] Found ${results.length} hospitals`);

  return results;
}

/**
 * Get hospital by ID - currently uses mock data
 * TODO: Implement real API call when endpoint is available
 */
export async function getHospitalByIdAPI(id: string): Promise<Hospital | null> {
  await delay(Math.random() * 500 + 300);

  const hospital = mockHospitals.find((h) => h.id === id);

  console.log(`[API] Fetching hospital with ID: ${id}`);
  console.log(`[API] Hospital found:`, hospital?.name || "Not found");

  return hospital || null;
}

/**
 * Get all hospitals - currently uses mock data
 * TODO: Implement real API call when endpoint is available
 */
export async function getAllHospitalsAPI(): Promise<Hospital[]> {
  await delay(Math.random() * 800 + 400);

  console.log(`[API] Fetching all hospitals`);
  console.log(`[API] Total hospitals: ${mockHospitals.length}`);

  return mockHospitals;
}

/**
 * Fetch doctors for a specific hospital (lazy loading)
 * Uses the real API endpoint: GET /hospitals/{hospitalId}/doctors?searchId={searchId}
 */
export async function getHospitalDoctorsAPI(hospitalId: string, searchId: string): Promise<Doctor[]> {
  if (!USE_REAL_API) {
    console.log(`[API] Mock mode - returning empty doctors array`);
    return [];
  }

  try {
    const url = `${API_BASE_URL}/hospitals/${hospitalId}/doctors?searchId=${searchId}`;
    console.log(`[API] Fetching doctors for hospital: ${hospitalId} | SearchId: ${searchId}`);

    const response = await fetch(url, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch doctors: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    console.log(`[API] Doctors fetched:`, data);

    // Adapt doctors to UI format
    const doctors = (data.doctors || []).map((d: any) => adaptEnrichedDoctorToDoctor(d));
    console.log(`[API] Found ${doctors.length} doctors for hospital ${hospitalId}`);

    return doctors;
  } catch (error) {
    console.error(`[API] Error fetching doctors for hospital ${hospitalId}:`, error);
    return []; // Return empty array on error
  }
}
