import { useState, useEffect, useRef } from "react";
import { Search, Sparkles } from "lucide-react";
import { HospitalCard } from "../components/HospitalCard";
import { Hospital } from "../data/mockData";
import { motion, AnimatePresence } from "motion/react";
import { LoadingSpinner } from "../components/LoadingSkeleton";
import { useSearch } from "../contexts/SearchContext";
import { AgentActivityStream } from "../components/AgentActivityStream";
import * as AppSync from "../services/appsync";
import type { AgentChunk } from "../services/appsync";

export function Home() {
  const { 
    searchResults: globalSearchResults, 
    setSearchResults: setGlobalSearchResults, 
    setSearchId: setGlobalSearchId,
    agentChunks: globalAgentChunks,
    setAgentChunks: setGlobalAgentChunks,
    isStreaming: globalIsStreaming,
    setIsStreaming: setGlobalIsStreaming
  } = useSearch();
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Hospital[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  
  // Use context for streaming state (persisted across navigation)
  const [agentChunks, setAgentChunks] = useState<string[]>(globalAgentChunks);
  const [isStreaming, setIsStreaming] = useState(globalIsStreaming);
  const subscriptionRef = useRef<any>(null);

  // Restore search results from context when component mounts
  useEffect(() => {
    if (globalSearchResults && globalSearchResults.length > 0) {
      setSearchResults(globalSearchResults);
      setHasSearched(true);
    }
    // Restore agent chunks
    if (globalAgentChunks && globalAgentChunks.length > 0) {
      setAgentChunks(globalAgentChunks);
    }
    // Restore streaming state
    setIsStreaming(globalIsStreaming);
  }, [globalSearchResults, globalAgentChunks, globalIsStreaming]);

  // Sync local state to context
  useEffect(() => {
    setGlobalAgentChunks(agentChunks);
  }, [agentChunks, setGlobalAgentChunks]);

  useEffect(() => {
    setGlobalIsStreaming(isStreaming);
  }, [isStreaming, setGlobalIsStreaming]);

  // Cleanup subscription on unmount
  useEffect(() => {
    return () => {
      if (subscriptionRef.current) {
        console.log('[Home] Cleaning up subscription');
        subscriptionRef.current.unsubscribe();
      }
    };
  }, []);

  /**
   * Get user's current location
   */
  const getUserLocation = async (): Promise<AppSync.LocationInput | undefined> => {
    return new Promise((resolve) => {
      if (!navigator.geolocation) {
        console.warn('[Home] Geolocation not supported');
        resolve(undefined);
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (position) => {
          const location = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          };
          console.log('[Home] User location obtained:', location);
          resolve(location);
        },
        (error) => {
          console.warn('[Home] Failed to get user location:', error.message);
          resolve(undefined);
        },
        {
          timeout: 5000,
          maximumAge: 300000, // Cache for 5 minutes
        }
      );
    });
  };

  /**
   * Convert AppSync Hospital to UI Hospital format
   */
  const adaptAppSyncHospital = (h: AppSync.Hospital): Hospital => {
    return {
      id: h.id,
      name: h.name,
      location: h.location,
      rating: h.rating,
      reviewCount: h.reviewCount,
      imageUrl: h.imageUrl || "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=400",
      description: h.description || "",
      specialties: h.specialties,
      acceptedInsurance: h.acceptedInsurance,
      avgCostRange: h.avgCostRange,
      aiRecommendation: h.aiRecommendation,
      insuranceCoveragePercent: h.insuranceCoveragePercent,
      trustScore: h.trustScore,
      verificationBadge: h.verificationBadge,
      coordinates: h.coordinates,
      distance: h.distance,
      topDoctorIds: h.topDoctorIds,
      doctors: [], // Lazy loaded
      reviews: h.reviews || [], // Include reviews from AppSync
      doctorAIReviews: h.doctorAIReviews || {},
    };
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!searchQuery.trim()) {
      return;
    }

    // Reset state
    setIsLoading(true);
    setHasSearched(true);
    setSearchResults([]);
    setAgentChunks([]);
    setIsStreaming(true);

    // Cleanup previous subscription
    if (subscriptionRef.current) {
      subscriptionRef.current.unsubscribe();
      subscriptionRef.current = null;
    }

    try {
      // Get user location
      const userLocation = await getUserLocation();

      // Enhance query with location if needed
      let enhancedQuery = searchQuery.replace(/\bnear\s+me\b/i, 'in Hyderabad');
      const hasLocation = /\b(in|near|at|around)\s+\w+/i.test(enhancedQuery) || 
                          /hyderabad|bangalore|mumbai|delhi|chennai|kolkata/i.test(enhancedQuery);
      
      if (!hasLocation) {
        enhancedQuery = `${enhancedQuery} in Hyderabad`;
        console.log(`[Home] No location detected, enhanced query: "${enhancedQuery}"`);
      }

      // Step 1: Initiate search via AppSync
      console.log('[Home] Initiating search via AppSync...');
      const { searchId, status } = await AppSync.initiateSearch(
        enhancedQuery,
        'test-user-123', // TODO: Get from auth context
        userLocation
      );

      if (status === 'error') {
        throw new Error('Failed to initiate search');
      }

      console.log('[Home] Search initiated:', searchId);
      setGlobalSearchId(searchId);

      // Step 2: Subscribe to agent activity
      console.log('[Home] Subscribing to agent activity...');
      subscriptionRef.current = AppSync.subscribeToAgentActivity(
        searchId,
        (chunk: AgentChunk) => {
          console.log('[Home] Received chunk:', chunk.chunk);
          setAgentChunks((prev) => [...prev, chunk.chunk]);
        },
        (error) => {
          console.error('[Home] Subscription error:', error);
          setIsStreaming(false);
        }
      );

      // Step 3: Poll for final results
      console.log('[Home] Polling for results...');
      const maxAttempts = 30;
      const pollInterval = 2000; // 2 seconds

      for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, pollInterval));

        const results = await AppSync.getSearchResults(searchId);
        console.log(`[Home] Poll attempt ${attempt}:`, results.status);

        if (results.status === 'complete') {
          console.log('[Home] Search complete!');
          setIsStreaming(false);

          if (results.results && results.results.hospitals) {
            const hospitals = results.results.hospitals.map(adaptAppSyncHospital);
            console.log(`[Home] Found ${hospitals.length} hospitals`);
            setSearchResults(hospitals);
            setGlobalSearchResults(hospitals);
          }

          // Cleanup subscription
          if (subscriptionRef.current) {
            subscriptionRef.current.unsubscribe();
            subscriptionRef.current = null;
          }

          break;
        }

        if (results.status === 'error') {
          throw new Error(results.error || 'Search failed');
        }

        // Still processing, continue polling
      }
    } catch (error) {
      console.error('[Home] Search failed:', error);
      setSearchResults([]);
      setGlobalSearchResults([]);
      setGlobalSearchId(null);
      setIsStreaming(false);
      
      // Cleanup subscription
      if (subscriptionRef.current) {
        subscriptionRef.current.unsubscribe();
        subscriptionRef.current = null;
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-full bg-gradient-to-b from-blue-50 to-white">
      {/* Hero Section */}
      <div className={`transition-all duration-500 ${hasSearched ? "py-8" : "py-24"}`}>
        <div className="max-w-4xl mx-auto px-6 text-center">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-8"
          >
            <div className="inline-flex items-center gap-2 bg-white px-4 py-2 rounded-full shadow-sm mb-6">
              <Sparkles className="w-4 h-4 text-blue-600" />
              <span className="text-sm font-medium text-gray-700">
                AI-Powered Healthcare Transparency
              </span>
            </div>
            <h1 className="text-4xl font-bold text-gray-900 mb-4">
              Find the Right Hospital for Your Needs
            </h1>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              Get verified information about costs, insurance coverage, and patient experiences
              to make informed healthcare decisions.
            </p>
          </motion.div>

          {/* Search Bar */}
          <motion.form
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            onSubmit={handleSearch}
            className="relative"
          >
            <div className="relative">
              <Search className="absolute left-5 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Describe your healthcare needs (e.g., 'affordable cardiac surgery with good insurance coverage')"
                className="w-full pl-14 pr-4 py-5 rounded-2xl border-2 border-gray-200 focus:border-blue-500 focus:outline-none text-base shadow-lg"
              />
            </div>
            <button
              type="submit"
              className="absolute right-2 top-1/2 transform -translate-y-1/2 bg-blue-600 text-white px-8 py-3 rounded-xl hover:bg-blue-700 transition-colors font-medium"
            >
              Search
            </button>
          </motion.form>

          {/* Search Suggestions */}
          {!hasSearched && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.4 }}
              className="mt-4 flex flex-wrap gap-2 justify-center"
            >
              <span className="text-sm text-gray-500">Try:</span>
              {["cardiac surgery", "orthopedic care", "cancer treatment", "affordable surgery"].map(
                (suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => setSearchQuery(suggestion)}
                    className="text-sm bg-white px-3 py-1 rounded-full border border-gray-200 hover:border-blue-500 hover:text-blue-600 transition-colors"
                  >
                    {suggestion}
                  </button>
                )
              )}
            </motion.div>
          )}
        </div>
      </div>

      {/* Search Results */}
      <AnimatePresence>
        {hasSearched && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="max-w-7xl mx-auto px-6 pb-12"
          >
            {/* Agent Activity Stream */}
            {(isStreaming || agentChunks.length > 0) && (
              <AgentActivityStream chunks={agentChunks} isActive={isStreaming} />
            )}

            {isLoading ? (
              <div className="text-center py-12">
                <LoadingSpinner className="w-16 h-16 text-blue-600" />
                <h3 className="text-xl font-semibold text-gray-900 mb-2 mt-4">Searching...</h3>
                <p className="text-gray-600">
                  AI agent is analyzing hospitals for you
                </p>
              </div>
            ) : searchResults.length > 0 ? (
              <>
                <div className="mb-6">
                  <h2 className="text-2xl font-semibold text-gray-900 mb-2">
                    Found {searchResults.length} hospitals matching your needs
                  </h2>
                  <p className="text-gray-600">
                    Click on any hospital to see detailed information and top doctors
                  </p>
                </div>

                <div className="space-y-6">
                  {searchResults.map((hospital) => (
                    <HospitalCard
                      key={hospital.id}
                      hospital={hospital}
                    />
                  ))}
                </div>
              </>
            ) : (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-center py-12"
              >
                <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Search className="w-8 h-8 text-gray-400" />
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">No results found</h3>
                <p className="text-gray-600">
                  Try adjusting your search terms or browse our complete hospital directory
                </p>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}