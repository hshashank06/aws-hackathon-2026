import { useState, useEffect } from 'react';

interface PartialHospital {
  hospitalId: string;
  hospitalName: string;
  address: string;
  phoneNumber: string;
  location: { latitude: number; longitude: number };
  aiReview: string;
}

interface FullHospital extends PartialHospital {
  services: string[];
  description: string;
  stats: {
    averageRating: number;
    totalReviews: number;
    averageCost: number;
  };
  topDoctors: Array<{
    doctorId: string;
    doctorName: string;
    specialty: string;
    experience: string;
  }>;
}

interface SearchState {
  status: 'idle' | 'searching' | 'partial' | 'complete' | 'error';
  progress: number;
  aiSummary?: string;
  hospitals: (PartialHospital | FullHospital)[];
  error?: string;
  stage?: string;
}

export function useProgressiveSearch(query: string) {
  const [state, setState] = useState<SearchState>({
    status: 'idle',
    progress: 0,
    hospitals: [],
  });

  useEffect(() => {
    if (!query) return;

    let pollInterval: number;
    let searchId: string;

    const initiateSearch = async () => {
      console.log('Initiating search with query:', query);
      setState({ status: 'searching', progress: 0, hospitals: [] });

      try {
        // Step 1: Initiate search
        console.log('Making POST request to /search');
        const response = await fetch('https://ri8zkgmzlb.execute-api.us-east-1.amazonaws.com/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query }),
        });

        console.log('POST response status:', response.status);
        
        if (!response.ok) {
          throw new Error('Failed to initiate search');
        }

        const data = await response.json();
        console.log('POST response data:', data);
        searchId = data.searchId;
        
        console.log('Search initiated, starting polling for:', searchId);

        // Step 2: Start polling
        pollInterval = window.setInterval(async () => {
          console.log('Polling for results:', searchId);
          try {
            const statusResponse = await fetch(`https://ri8zkgmzlb.execute-api.us-east-1.amazonaws.com/search/${searchId}`);
            
            if (!statusResponse.ok) {
              throw new Error('Failed to fetch search status');
            }

            const statusData = await statusResponse.json();

            if (statusData.status === 'processing') {
              // Update with partial results
              const partial = statusData.partialResults;
              
              if (partial) {
                setState({
                  status: 'partial',
                  progress: statusData.progress || 0,
                  aiSummary: partial.aiSummary,
                  hospitals: partial.hospitals || [],
                  stage: partial.stage,
                });
              } else {
                setState(prev => ({
                  ...prev,
                  progress: statusData.progress || 0,
                }));
              }
            } else if (statusData.status === 'complete') {
              // Final results
              window.clearInterval(pollInterval);
              const results = statusData.results?.results;
              setState({
                status: 'complete',
                progress: 100,
                aiSummary: results?.aiSummary || statusData.results?.userIntent?.aiSummary,
                hospitals: results?.hospitals || [],
              });
            } else if (statusData.status === 'error') {
              window.clearInterval(pollInterval);
              setState({
                status: 'error',
                progress: 0,
                hospitals: [],
                error: statusData.error || 'An error occurred',
              });
            }
          } catch (error) {
            console.error('Polling error:', error);
            // Continue polling - don't fail on single poll error
          }
        }, 2000); // Poll every 2 seconds
      } catch (error) {
        console.error('Search initiation failed:', error);
        setState({
          status: 'error',
          progress: 0,
          hospitals: [],
          error: error instanceof Error ? error.message : 'Failed to initiate search',
        });
      }
    };

    initiateSearch();

    return () => {
      if (pollInterval) window.clearInterval(pollInterval);
    };
  }, [query]);

  return state;
}

// Main component
export function ProgressiveSearchResults({ query }: { query: string }) {
  const { status, progress, aiSummary, hospitals, error } = useProgressiveSearch(query);

  if (status === 'idle') {
    return null;
  }

  if (status === 'error') {
    return (
      <div className="rounded-lg bg-red-50 p-4 text-red-800">
        <h3 className="font-semibold">Search Error</h3>
        <p>{error}</p>
      </div>
    );
  }

  const isPartial = status === 'partial';
  const isComplete = status === 'complete';

  return (
    <div className="space-y-6">
      {/* Progress bar */}
      {!isComplete && (
        <div className="sticky top-0 z-10 bg-white pb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">
              {status === 'searching' && progress === 0 && 'Starting search...'}
              {progress > 0 && progress < 30 && 'Analyzing your query...'}
              {progress >= 30 && progress < 60 && 'Fetching hospital data...'}
              {progress >= 60 && 'Loading detailed information...'}
            </span>
            <span className="text-sm font-semibold text-blue-600">{progress}%</span>
          </div>
          <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-blue-500 to-green-500 transition-all duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Initial loading state */}
      {status === 'searching' && hospitals.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-gray-600">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4" />
          <p className="text-lg font-medium">Searching for hospitals...</p>
          <p className="text-sm text-gray-500 mt-2">This may take 30-40 seconds</p>
        </div>
      )}

      {/* AI Summary - shows at 30% */}
      {aiSummary && (
        <div className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded-r-lg animate-fade-in">
          <h3 className="text-lg font-semibold text-blue-900 mb-2">
            🤖 AI Recommendations
          </h3>
          <p className="text-blue-800">{aiSummary}</p>
        </div>
      )}

      {/* Hospital cards */}
      {hospitals.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-2xl font-bold text-gray-900">
            {isComplete ? 'Search Results' : 'Loading Results...'}
          </h2>
          
          <div className="grid gap-6">
            {hospitals.map((hospital) => (
              <HospitalCard
                key={hospital.hospitalId}
                hospital={hospital}
                isPartial={isPartial}
              />
            ))}
          </div>
        </div>
      )}

      {/* Loading indicator */}
      {!isComplete && hospitals.length > 0 && (
        <div className="flex items-center justify-center py-8 text-gray-600">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3" />
          <p>Loading detailed information...</p>
        </div>
      )}
    </div>
  );
}

// Hospital card component
function HospitalCard({ 
  hospital, 
  isPartial 
}: { 
  hospital: PartialHospital | FullHospital; 
  isPartial: boolean;
}) {
  const isFullHospital = (h: PartialHospital | FullHospital): h is FullHospital => {
    return 'stats' in h;
  };

  return (
    <div 
      className={`
        bg-white rounded-lg shadow-md overflow-hidden transition-all duration-500
        ${isPartial ? 'border-l-4 border-yellow-400' : 'border-l-4 border-green-500'}
        animate-fade-in
      `}
    >
      <div className="p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-xl font-bold text-gray-900">{hospital.hospitalName}</h3>
            <p className="text-gray-600 mt-1">{hospital.address}</p>
            <p className="text-blue-600 mt-1">📞 {hospital.phoneNumber}</p>
          </div>
          {isPartial && (
            <span className="px-3 py-1 bg-yellow-100 text-yellow-800 text-xs font-semibold rounded-full">
              Loading...
            </span>
          )}
        </div>

        {/* AI Review */}
        {hospital.aiReview && (
          <div className="bg-gray-50 rounded-lg p-4 mb-4">
            <p className="text-sm text-gray-700 italic">{hospital.aiReview}</p>
          </div>
        )}

        {/* Skeleton loaders for partial data */}
        {isPartial && (
          <div className="space-y-3 animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-3/4" />
            <div className="h-4 bg-gray-200 rounded w-1/2" />
            <div className="h-4 bg-gray-200 rounded w-5/6" />
          </div>
        )}

        {/* Full data */}
        {!isPartial && isFullHospital(hospital) && (
          <>
            {/* Stats */}
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="text-center p-3 bg-blue-50 rounded-lg">
                <div className="text-2xl font-bold text-blue-600">
                  {hospital.stats.averageRating.toFixed(1)}
                </div>
                <div className="text-xs text-gray-600">Rating</div>
              </div>
              <div className="text-center p-3 bg-green-50 rounded-lg">
                <div className="text-2xl font-bold text-green-600">
                  {hospital.stats.totalReviews}
                </div>
                <div className="text-xs text-gray-600">Reviews</div>
              </div>
              <div className="text-center p-3 bg-purple-50 rounded-lg">
                <div className="text-lg font-bold text-purple-600">
                  ₹{hospital.stats.averageCost.toLocaleString()}
                </div>
                <div className="text-xs text-gray-600">Avg Cost</div>
              </div>
            </div>

            {/* Top Doctors */}
            {hospital.topDoctors && hospital.topDoctors.length > 0 && (
              <div className="border-t pt-4">
                <h4 className="font-semibold text-gray-900 mb-3">Top Doctors</h4>
                <div className="space-y-2">
                  {hospital.topDoctors.map((doctor) => (
                    <div 
                      key={doctor.doctorId}
                      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                    >
                      <div>
                        <p className="font-medium text-gray-900">{doctor.doctorName}</p>
                        <p className="text-sm text-gray-600">
                          {doctor.specialty} • {doctor.experience}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// Add this to your global CSS (tailwind.css or index.css)
/*
@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in {
  animation: fade-in 0.5s ease-out;
}
*/
