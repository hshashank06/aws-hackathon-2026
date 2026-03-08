/**
 * AWS AppSync Client for Hospital Search Streaming
 * Handles GraphQL mutations, queries, and real-time subscriptions
 */

import { Amplify } from 'aws-amplify';
import { generateClient } from 'aws-amplify/api';

// AppSync Configuration
const APPSYNC_CONFIG = {
  endpoint: 'https://xg5bjurpsbgfda2nufr6c46n7e.appsync-api.us-east-1.amazonaws.com/graphql',
  region: 'us-east-1',
  apiKey: 'da2-ezoxtcpclffrdkbysmv22sjiei',
};

// Configure Amplify
Amplify.configure({
  API: {
    GraphQL: {
      endpoint: APPSYNC_CONFIG.endpoint,
      region: APPSYNC_CONFIG.region,
      defaultAuthMode: 'apiKey',
      apiKey: APPSYNC_CONFIG.apiKey,
    },
  },
});

// Create GraphQL client
const client = generateClient();

// GraphQL Operations
const INITIATE_SEARCH = `
  mutation InitiateSearch($query: String!, $customerId: String, $userLocation: LocationInput) {
    initiateSearch(query: $query, customerId: $customerId, userLocation: $userLocation) {
      searchId
      status
    }
  }
`;

const GET_SEARCH_RESULTS = `
  query GetSearchResults($searchId: ID!) {
    getSearchResults(searchId: $searchId) {
      searchId
      status
      results {
        aiSummary
        hospitals {
          id
          name
          location
          rating
          reviewCount
          imageUrl
          description
          specialties
          acceptedInsurance
          avgCostRange {
            min
            max
          }
          hospitalAIReview
          insuranceCoveragePercent
          trustScore
          verificationBadge
          coordinates {
            latitude
            longitude
          }
          distance
          topDoctorIds
          reviews {
            id
            patientName
            rating
            date
            treatment
            cost
            insuranceCovered
            comment
            verified
          }
          doctorAIReviews
        }
      }
      error
    }
  }
`;

const SUBSCRIBE_AGENT_ACTIVITY = `
  subscription OnAgentActivity($searchId: ID!) {
    onAgentActivity(searchId: $searchId) {
      searchId
      chunk
      timestamp
    }
  }
`;

// Types
export interface LocationInput {
  latitude: number;
  longitude: number;
}

export interface SearchInitiatedResponse {
  searchId: string;
  status: string;
}

export interface AgentChunk {
  searchId: string;
  chunk: string;
  timestamp: string;
}

export interface Hospital {
  id: string;
  name: string;
  location: string;
  rating: number;
  reviewCount: number;
  imageUrl?: string;
  description?: string;
  specialties: string[];
  acceptedInsurance: string[];
  avgCostRange: {
    min: number;
    max: number;
  };
  aiRecommendation: string;
  hospitalAIReview?: string;
  insuranceCoveragePercent: number;
  trustScore: number;
  verificationBadge: string;
  coordinates?: {
    latitude: number;
    longitude: number;
  };
  distance?: number;
  topDoctorIds: string[];
  reviews: Review[];
  doctorAIReviews?: any;
}

export interface Review {
  id: string;
  patientName: string;
  rating?: number;
  date: string;
  treatment: string;
  cost: number;
  insuranceCovered: number;
  comment: string;
  verified: boolean;
}

export interface SearchResults {
  searchId: string;
  status: string;
  results?: {
    aiSummary: string;
    hospitals: Hospital[];
  };
  error?: string;
}

/**
 * Initiate a new hospital search
 */
export async function initiateSearch(
  query: string,
  customerId?: string,
  userLocation?: LocationInput
): Promise<SearchInitiatedResponse> {
  try {
    console.log('[AppSync] Initiating search:', { query, customerId, userLocation });

    const response: any = await client.graphql({
      query: INITIATE_SEARCH,
      variables: {
        query,
        customerId: customerId || 'anonymous',
        userLocation,
      },
    });

    const data = response.data.initiateSearch;
    console.log('[AppSync] Search initiated:', data);

    return data;
  } catch (error) {
    console.error('[AppSync] Failed to initiate search:', error);
    throw error;
  }
}

/**
 * Subscribe to agent activity for a specific search
 * Returns an observable that emits chunks as they arrive
 */
export function subscribeToAgentActivity(
  searchId: string,
  onChunk: (chunk: AgentChunk) => void,
  onError?: (error: any) => void
) {
  console.log('[AppSync] Subscribing to agent activity:', searchId);

  const subscription = (client.graphql({
    query: SUBSCRIBE_AGENT_ACTIVITY,
    variables: { searchId },
  }) as any).subscribe({
    next: ({ data }: any) => {
      const chunk = data.onAgentActivity;
      console.log('[AppSync] Received chunk:', chunk);
      onChunk(chunk);
    },
    error: (error: any) => {
      console.error('[AppSync] Subscription error:', error);
      if (onError) onError(error);
    },
  });

  return subscription;
}

/**
 * Get final search results from DynamoDB
 */
export async function getSearchResults(searchId: string): Promise<SearchResults> {
  try {
    console.log('[AppSync] Fetching search results:', searchId);

    const response: any = await client.graphql({
      query: GET_SEARCH_RESULTS,
      variables: { searchId },
    });

    const data = response.data.getSearchResults;
    console.log('[AppSync] Search results:', data);

    return data;
  } catch (error) {
    console.error('[AppSync] Failed to fetch search results:', error);
    throw error;
  }
}
