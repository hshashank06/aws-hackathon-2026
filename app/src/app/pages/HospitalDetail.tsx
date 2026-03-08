import { useParams, Link } from "react-router-dom";
import { useState, useEffect } from "react";
import { ArrowLeft, MapPin, Star, IndianRupee, Shield, Phone, Clock, ChevronRight, CheckCircle, XCircle, Navigation } from "lucide-react";
import { motion } from "motion/react";
import { Hospital, Doctor } from "../data/mockData";
import { getHospitalByIdAPI } from "../services/api";
import { DoctorCard } from "../components/DoctorCard";
import { HospitalMap } from "../components/HospitalMap";
import ReactMarkdown from "react-markdown";
import { useSearch } from "../contexts/SearchContext";

// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "https://ri8zkgmzlb.execute-api.us-east-1.amazonaws.com";

export function HospitalDetail() {
  const { id } = useParams();
  const [hospital, setHospital] = useState<Hospital | null>(null);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDoctorsLoading, setIsDoctorsLoading] = useState(false);
  const [isDescriptionExpanded, setIsDescriptionExpanded] = useState(false);
  const [expandedReviews, setExpandedReviews] = useState<Set<string>>(new Set());
  const [acceptedInsurance, setAcceptedInsurance] = useState<string[]>([]);
  const [userLocation, setUserLocation] = useState<{ latitude: number; longitude: number } | null>(null);
  const { getHospitalById, searchId } = useSearch();

  // Get user location on mount
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setUserLocation({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          });
        },
        (error) => {
          console.warn("Failed to get user location:", error);
        }
      );
    }
  }, []);

  const toggleReviewExpansion = (reviewId: string) => {
    setExpandedReviews(prev => {
      const newSet = new Set(prev);
      if (newSet.has(reviewId)) {
        newSet.delete(reviewId);
      } else {
        newSet.add(reviewId);
      }
      return newSet;
    });
  };

  const truncateReview = (text: string, maxSentences: number = 4) => {
    // Split by sentence endings (., !, ?)
    const sentences = text.match(/[^.!?]+[.!?]+/g) || [text];
    if (sentences.length <= maxSentences) {
      return { truncated: text, needsTruncation: false };
    }
    const truncated = sentences.slice(0, maxSentences).join(' ');
    return { truncated, needsTruncation: true };
  };

  useEffect(() => {
    async function fetchHospital() {
      if (!id) return;
      
      setIsLoading(true);
      try {
        // First try to get from search context (real API results)
        const contextHospital = getHospitalById(id);
        
        if (contextHospital) {
          console.log("[HospitalDetail] Found hospital in search context");
          console.log("[HospitalDetail] Full hospital object:", contextHospital);
          setHospital(contextHospital);
          
          // Fetch insurance companies for this hospital
          const fetchInsuranceCompanies = async () => {
            try {
              // First, fetch the full hospital data to get insuranceCompanyIds
              const hospitalResponse = await fetch(
                `${API_BASE_URL}/hospitals/${id}`
              );
              if (hospitalResponse.ok) {
                const hospitalData = await hospitalResponse.json();
                const insuranceIds = hospitalData.insuranceCompanyIds || [];
                
                if (insuranceIds.length > 0) {
                  console.log("[HospitalDetail] Fetching insurance companies:", insuranceIds);
                  
                  // Fetch each insurance company
                  const insurancePromises = insuranceIds.map(async (insuranceId: string) => {
                    try {
                      const response = await fetch(
                        `${API_BASE_URL}/insurance-companies/${insuranceId}`
                      );
                      if (response.ok) {
                        const data = await response.json();
                        console.log(`[HospitalDetail] Insurance ${insuranceId} full response:`, JSON.stringify(data, null, 2));
                        console.log(`[HospitalDetail] Insurance ${insuranceId} name field:`, data.insuranceCompanyName);
                        console.log(`[HospitalDetail] Insurance ${insuranceId} all keys:`, Object.keys(data));
                        // Return the name, or null if name is not available
                        return data.insuranceCompanyName || data.name || null;
                      } else {
                        const errorText = await response.text();
                        console.warn(`[HospitalDetail] Failed to fetch insurance ${insuranceId}: ${response.status}`, errorText);
                        return null; // Return null for failed fetches
                      }
                    } catch (error) {
                      console.error(`Failed to fetch insurance ${insuranceId}:`, error);
                      return null; // Return null for errors
                    }
                  });
                  
                  const insuranceResults = await Promise.all(insurancePromises);
                  // Filter out null values (failed fetches)
                  const insuranceNames = insuranceResults.filter((name): name is string => name !== null);
                  console.log("[HospitalDetail] Fetched insurance names:", insuranceNames);
                  
                  if (insuranceNames.length > 0) {
                    setAcceptedInsurance(insuranceNames);
                  } else {
                    // If all fetches failed, use defaults
                    console.log("[HospitalDetail] All insurance fetches failed, using defaults");
                    setAcceptedInsurance(["Blue Cross", "United Health", "Aetna", "Medicare"]);
                  }
                } else {
                  console.log("[HospitalDetail] No insurance IDs found, using defaults");
                  // Fallback to default list
                  setAcceptedInsurance(["Blue Cross", "United Health", "Aetna", "Medicare"]);
                }
              } else {
                console.warn("[HospitalDetail] Failed to fetch hospital data:", hospitalResponse.status);
                setAcceptedInsurance(["Blue Cross", "United Health", "Aetna", "Medicare"]);
              }
            } catch (error) {
              console.error("[HospitalDetail] Failed to fetch insurance companies:", error);
              // Fallback to default list
              setAcceptedInsurance(["Blue Cross", "United Health", "Aetna", "Medicare"]);
            }
          };
          
          fetchInsuranceCompanies();
          
          // Check if hospital has topDoctorIds - these are the doctor IDs from LLM
          if (contextHospital.topDoctorIds && contextHospital.topDoctorIds.length > 0) {
            console.log("[HospitalDetail] Found topDoctorIds:", contextHospital.topDoctorIds);
            console.log("[HospitalDetail] doctorAIReviews:", contextHospital.doctorAIReviews);
            setIsDoctorsLoading(true);
            
            try {
              // Get doctor AI reviews from the hospital object
              const doctorAIReviews = contextHospital.doctorAIReviews || {};
              console.log("[HospitalDetail] Using doctorAIReviews mapping:", doctorAIReviews);
              
              // Fetch doctors from LLM recommendations
              const doctorPromises = contextHospital.topDoctorIds.map(async (doctorId: string) => {
                try {
                  // Fetch doctor data
                  const doctorResponse = await fetch(
                    `${API_BASE_URL}/doctors/${doctorId}`
                  );
                  if (!doctorResponse.ok) {
                    console.error(`Failed to fetch doctor ${doctorId}`);
                    return null;
                  }
                  const doctorData = await doctorResponse.json();
                  
                  // Fetch doctor reviews to get review count
                  let reviewCount = 0;
                  try {
                    const reviewsResponse = await fetch(
                      `${API_BASE_URL}/reviews?doctorId=${doctorId}&limit=100`
                    );
                    if (reviewsResponse.ok) {
                      const reviewsData = await reviewsResponse.json();
                      reviewCount = reviewsData.count || 0;
                      console.log(`[HospitalDetail] Doctor ${doctorId} has ${reviewCount} reviews`);
                    }
                  } catch (error) {
                    console.warn(`Failed to fetch reviews for doctor ${doctorId}:`, error);
                  }
                  
                  // Get AI review for this doctor
                  let aiReview = doctorAIReviews[doctorId] || "";
                  console.log(`[HospitalDetail] Doctor ${doctorId} AI review:`, aiReview ? "Found" : "EMPTY");
                  
                  // Replace doctor ID with actual doctor name in AI review
                  // LLM sometimes uses "Dr. doctor_xyz" format, replace with actual name
                  const doctorName = doctorData.doctorName || "Unknown Doctor";
                  if (aiReview && doctorId) {
                    // Replace patterns like "Dr. doctor_xyz" or "doctor_xyz" with actual name
                    aiReview = aiReview.replace(new RegExp(`Dr\\.?\\s*${doctorId}`, 'gi'), doctorName);
                    aiReview = aiReview.replace(new RegExp(doctorId, 'gi'), doctorName);
                    
              
                  }
                  
                  // Extract qualifications from 'about' field since Doctor table doesn't have qualifications field
                  const qualifications: string[] = [];
                  const about = doctorData.about || "";
                  
                  // Look for common qualification patterns in the about text
                  const qualMatches = about.match(/\b(MBBS|MD|MS|MCh|DM|DNB|FRCS|MRCP|PhD|Fellowship|Board Certified)\b/gi);
                  if (qualMatches && qualMatches.length > 0) {
                    // Remove duplicates and limit to first 5
                    const seen = new Set<string>();
                    for (const qual of qualMatches) {
                      const upper = qual.toUpperCase();
                      if (!seen.has(upper) && qualifications.length < 5) {
                        seen.add(upper);
                        qualifications.push(upper);
                      }
                    }
                    console.log(`[HospitalDetail] Extracted qualifications for ${doctorId}:`, qualifications);
                  } else {
                    console.log(`[HospitalDetail] No qualifications found in about text for ${doctorId}`);
                  }
                  
                  // Transform to UI format
                  return {
                    id: doctorData.doctorId,
                    name: doctorName,
                    specialty: doctorData.specialty || "General",
                    experience: doctorData.yearsOfExperience || 10,
                    qualifications: qualifications,
                    rating: doctorData.rating || 4.5,
                    reviewCount: reviewCount,  // Use fetched review count
                    imageUrl: "https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=200",  // Use real image URL
                    aiSummary: aiReview, // Use AI review from hospital object
                    about: about,  // Add doctor description
                    reviews: [],
                  };
                } catch (error) {
                  console.error(`Error fetching doctor ${doctorId}:`, error);
                  return null;
                }
              });
              
              let fetchedDoctors = (await Promise.all(doctorPromises)).filter(d => d !== null);
              console.log("[HospitalDetail] Fetched doctors from LLM:", fetchedDoctors.length);
              
              // If less than 3 doctors, fetch additional doctors from hospital departments
              if (fetchedDoctors.length < 3) {
                console.log("[HospitalDetail] Less than 3 doctors, fetching additional from hospital departments");
                try {
                  // Fetch hospital data to get department IDs
                  const hospitalResponse = await fetch(
                    `${API_BASE_URL}/hospitals/${id}`
                  );
                  if (hospitalResponse.ok) {
                    const hospitalData = await hospitalResponse.json();
                    const departmentIds = hospitalData.departmentIds || [];
                    console.log("[HospitalDetail] Hospital has departments:", departmentIds);
                    
                    // Fetch doctors for each department using departmentId query parameter
                    const allDoctorIds: string[] = [];
                    for (const deptId of departmentIds) {
                      try {
                        const doctorsResponse = await fetch(
                          `${API_BASE_URL}/doctors?departmentId=${deptId}&limit=100`
                        );
                        if (doctorsResponse.ok) {
                          const doctorsData = await doctorsResponse.json();
                          const deptDoctorIds = (doctorsData.items || []).map((d: any) => d.doctorId);
                          allDoctorIds.push(...deptDoctorIds);
                          console.log(`[HospitalDetail] Department ${deptId} has ${deptDoctorIds.length} doctors`);
                        }
                      } catch (error) {
                        console.warn(`Failed to fetch doctors for department ${deptId}:`, error);
                      }
                    }
                    
                    console.log("[HospitalDetail] Total doctors from all departments:", allDoctorIds.length);
                    
                    // Filter out doctors we already have
                    const existingDoctorIds = new Set(fetchedDoctors.map(d => d.id));
                    const additionalDoctorIds = allDoctorIds.filter((did: string) => !existingDoctorIds.has(did));
                    
                    console.log("[HospitalDetail] Fetching additional doctors to sort:", additionalDoctorIds.length);
                    
                    // Fetch ALL additional doctors (so we can sort them)
                    const additionalPromises = additionalDoctorIds.map(async (doctorId: string) => {
                      try {
                        const doctorResponse = await fetch(
                          `${API_BASE_URL}/doctors/${doctorId}`
                        );
                        if (!doctorResponse.ok) return null;
                        
                        const doctorData = await doctorResponse.json();
                        
                        // Fetch review count
                        let reviewCount = 0;
                        try {
                          const reviewsResponse = await fetch(
                            `${API_BASE_URL}/reviews?doctorId=${doctorId}&limit=100`
                          );
                          if (reviewsResponse.ok) {
                            const reviewsData = await reviewsResponse.json();
                            reviewCount = reviewsData.count || 0;
                          }
                        } catch (error) {
                          console.warn(`Failed to fetch reviews for additional doctor ${doctorId}:`, error);
                        }
                        
                        // Extract qualifications
                        const qualifications: string[] = [];
                        const about = doctorData.about || "";
                        const qualMatches = about.match(/\b(MBBS|MD|MS|MCh|DM|DNB|FRCS|MRCP|PhD|Fellowship|Board Certified)\b/gi);
                        if (qualMatches) {
                          const seen = new Set<string>();
                          for (const qual of qualMatches) {
                            const upper = qual.toUpperCase();
                            if (!seen.has(upper) && qualifications.length < 5) {
                              seen.add(upper);
                              qualifications.push(upper);
                            }
                          }
                        }
                        
                        return {
                          id: doctorData.doctorId,
                          name: doctorData.doctorName || "Unknown Doctor",
                          specialty: doctorData.specialty || "General",
                          experience: doctorData.yearsOfExperience || 10,
                          qualifications: qualifications,
                          rating: doctorData.rating || 4.5,
                          reviewCount: reviewCount,
                          imageUrl: "https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=200",
                          aiSummary: "",  // No AI review for additional doctors
                          about: about,
                          reviews: [],
                        };
                      } catch (error) {
                        console.error(`Error fetching additional doctor ${doctorId}:`, error);
                        return null;
                      }
                    });
                    
                    let additionalDoctors = (await Promise.all(additionalPromises)).filter(d => d !== null);
                    
                    // Sort by rating (descending) and review count (descending) to get top doctors
                    additionalDoctors.sort((a, b) => {
                      // First sort by rating
                      if (b.rating !== a.rating) {
                        return b.rating - a.rating;
                      }
                      // If ratings are equal, sort by review count
                      return b.reviewCount - a.reviewCount;
                    });
                    
                    // Take only the top doctors we need to reach 3 total
                    const neededCount = 3 - fetchedDoctors.length;
                    additionalDoctors = additionalDoctors.slice(0, neededCount);
                    
                    console.log("[HospitalDetail] Selected top additional doctors:", additionalDoctors.length);
                    fetchedDoctors = [...fetchedDoctors, ...additionalDoctors];
                    console.log("[HospitalDetail] Total doctors after adding additional:", fetchedDoctors.length);
                  }
                } catch (error) {
                  console.error("[HospitalDetail] Failed to fetch additional doctors:", error);
                }
              }
              
              console.log("[HospitalDetail] Final doctor count:", fetchedDoctors.length);
              console.log("[HospitalDetail] Doctors with AI reviews:", fetchedDoctors.filter(d => d.aiSummary).length);
              setDoctors(fetchedDoctors);
            } catch (error) {
              console.error("[HospitalDetail] Failed to fetch doctors:", error);
              setDoctors([]);
            } finally {
              setIsDoctorsLoading(false);
            }
          } else {
            console.warn("[HospitalDetail] No topDoctorIds available");
            setDoctors([]);
          }
        } else {
          // Fallback to mock data
          console.log("[HospitalDetail] Hospital not in context, fetching from API");
          const data = await getHospitalByIdAPI(id);
          setHospital(data);
          // Use doctors from mock data
          setDoctors(data?.doctors || []);
        }
      } catch (error) {
        console.error("Failed to fetch hospital:", error);
      } finally {
        setIsLoading(false);
      }
    }

    fetchHospital();
  }, [id, getHospitalById, searchId]);

  if (isLoading) {
    return (
      <div className="min-h-full bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <motion.div
            className="w-16 h-16 border-4 border-blue-200 border-t-blue-600 rounded-full mx-auto mb-4"
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Loading hospital details...</h2>
        </div>
      </div>
    );
  }

  if (!hospital) {
    return (
      <div className="min-h-full bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Hospital Not Found</h2>
          <Link to="/" className="text-blue-600 hover:underline">
            Return to Home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-full bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Search
          </Link>

          <div className="flex gap-6">
            <img
              src={hospital.imageUrl}
              alt={hospital.name}
              className="w-32 h-32 rounded-lg object-cover"
              onError={(e) => {
                e.currentTarget.src = "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=400";
              }}
            />
            <div className="flex-1">
              <h1 className="text-3xl font-bold text-gray-900 mb-2">{hospital.name}</h1>
              <div className="flex items-center gap-2 text-gray-600 mb-3">
                <MapPin className="w-4 h-4" />
                <span>{hospital.location}</span>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1">
                  <Star className="w-5 h-5 fill-yellow-400 text-yellow-400" />
                  <span className="font-semibold">{hospital.rating}</span>
                  <span className="text-gray-500">({hospital.reviewCount} reviews)</span>
                </div>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <button className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors font-medium">
                Write a Review
              </button>
              <button className="border border-gray-300 px-6 py-2 rounded-lg hover:bg-gray-50 transition-colors font-medium">
                Contact Hospital
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* About */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-white rounded-lg border border-gray-200 p-6"
            >
              <h2 className="text-xl font-semibold text-gray-900 mb-4">About</h2>
              <div className={`prose max-w-none text-gray-700 mb-4 ${!isDescriptionExpanded ? 'line-clamp-5' : ''}`}>
                <ReactMarkdown>{hospital.description}</ReactMarkdown>
              </div>
              {hospital.description && hospital.description.split('\n').length > 5 && (
                <button
                  onClick={() => setIsDescriptionExpanded(!isDescriptionExpanded)}
                  className="text-blue-600 hover:text-blue-700 font-medium text-sm"
                >
                  {isDescriptionExpanded ? 'Show less' : 'Read more...'}
                </button>
              )}

              <div className="grid grid-cols-4 gap-4 mt-4 mb-4">
                <div className="bg-blue-50 rounded-lg p-4">
                  <div className="flex items-center gap-2 text-blue-700 text-sm font-medium mb-2">
                    <IndianRupee className="w-4 h-4" />
                    <span>Cost Range</span>
                  </div>
                  <p className="text-lg font-semibold">
                    ₹{(hospital.avgCostRange.min / 1000).toFixed(0)}k - ₹
                    {(hospital.avgCostRange.max / 1000).toFixed(0)}k
                  </p>
                </div>
                <div className="bg-green-50 rounded-lg p-4">
                  <div className="flex items-center gap-2 text-green-700 text-sm font-medium mb-2">
                    <Shield className="w-4 h-4" />
                    <span>Specialties</span>
                  </div>
                  <p className="text-lg font-semibold">{hospital.specialties.length}</p>
                </div>
                <div className="bg-purple-50 rounded-lg p-4">
                  <div className="flex items-center gap-2 text-purple-700 text-sm font-medium mb-2">
                    <Star className="w-4 h-4" />
                    <span>Rating</span>
                  </div>
                  <p className="text-lg font-semibold">{hospital.rating}/5.0</p>
                </div>
                <div className="bg-orange-50 rounded-lg p-4">
                  <div className="flex items-center gap-2 text-orange-700 text-sm font-medium mb-2">
                    <Phone className="w-4 h-4" />
                    <span>Contact</span>
                  </div>
                  <p className="text-sm font-semibold">(555) 123-4567</p>
                </div>
              </div>

              <div>
                <h3 className="font-semibold text-gray-900 mb-2">Specialties</h3>
                <div className="flex flex-wrap gap-2">
                  {hospital.specialties.map((specialty) => (
                    <span
                      key={specialty}
                      className="px-3 py-1.5 bg-blue-100 text-blue-700 rounded-full text-sm font-medium"
                    >
                      {specialty}
                    </span>
                  ))}
                </div>
              </div>
            </motion.div>

            {/* AI Recommendation */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg border border-blue-200 p-6"
            >
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-bold">AI</span>
                </div>
                <h2 className="text-xl font-semibold text-gray-900">AI Analysis</h2>
              </div>
              <div className="prose max-w-none text-gray-700">
                <ReactMarkdown>{hospital.hospitalAIReview || hospital.aiRecommendation}</ReactMarkdown>
              </div>
            </motion.div>

            {/* Our Doctors */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="bg-white rounded-lg border border-gray-200 p-6"
            >
              <h2 className="text-xl font-semibold text-gray-900 mb-4">Our Top Doctors</h2>
              {isDoctorsLoading ? (
                <div className="text-center py-8">
                  <motion.div
                    className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full mx-auto mb-3"
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  />
                  <p className="text-gray-600 text-sm">Loading doctors...</p>
                </div>
              ) : doctors.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {doctors.map((doctor, index) => (
                    <DoctorCard key={doctor.id} doctor={doctor} index={index} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <p>No doctor information available</p>
                </div>
              )}
            </motion.div>

            {/* Patient Reviews */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="bg-white rounded-lg border border-gray-200 p-6"
            >
              <h2 className="text-xl font-semibold text-gray-900 mb-4">Patient Reviews</h2>
              <div className="space-y-4">
                {hospital.reviews.map((review) => {
                  const isExpanded = expandedReviews.has(review.id);
                  const { truncated, needsTruncation } = truncateReview(review.comment);
                  const displayText = isExpanded ? review.comment : truncated;
                  
                  return (
                    <div key={review.id} className="border-b border-gray-200 last:border-0 pb-4 last:pb-0">
                      <div className="flex items-center gap-3 mb-2">
                        {review.rating != null && review.rating > 0 && (
                          <div className="flex">
                            {[...Array(5)].map((_, i) => (
                              <Star
                                key={i}
                                className={`w-4 h-4 ${
                                  i < (review.rating || 0)
                                    ? "fill-yellow-400 text-yellow-400"
                                    : "text-gray-300"
                                }`}
                              />
                            ))}
                          </div>
                        )}
                        {review.patientName && review.patientName !== "Anonymous" && (
                          <span className="font-medium text-gray-900">{review.patientName}</span>
                        )}
                        {review.verified ? (
                          <div className="flex items-center gap-1 bg-green-50 text-green-700 px-2 py-1 rounded">
                            <CheckCircle className="w-3.5 h-3.5" />
                            <span className="text-xs font-medium">Verified Patient</span>
                          </div>
                        ) : (
                          <div className="flex items-center gap-1 bg-red-50 text-red-700 px-2 py-1 rounded">
                            <XCircle className="w-3.5 h-3.5" />
                            <span className="text-xs font-medium">Unverified</span>
                          </div>
                        )}
                        <span className="text-sm text-gray-500 ml-auto">{review.date}</span>
                      </div>
                      <p className="font-medium text-gray-900 mb-2">{review.treatment}</p>
                      <div className="text-gray-700 mb-2 prose prose-sm max-w-none">
                        <ReactMarkdown>{displayText}</ReactMarkdown>
                      </div>
                      {needsTruncation && (
                        <button
                          onClick={() => toggleReviewExpansion(review.id)}
                          className="text-blue-600 hover:text-blue-700 font-medium text-sm mb-3"
                        >
                          {isExpanded ? 'Show less' : 'Read more...'}
                        </button>
                      )}
                      <div className="flex gap-4 text-sm">
                        <div className="bg-gray-50 px-3 py-2 rounded">
                          <span className="text-gray-600">Total Cost: </span>
                          <span className="font-semibold">₹{review.cost.toLocaleString()}</span>
                        </div>
                        <div className="bg-green-50 px-3 py-2 rounded">
                          <span className="text-gray-600">Insurance Covered: </span>
                          <span className="font-semibold text-green-700">
                            ₹{review.insuranceCovered.toLocaleString()}
                          </span>
                        </div>
                        <div className="bg-blue-50 px-3 py-2 rounded">
                          <span className="text-gray-600">Out of Pocket: </span>
                          <span className="font-semibold text-blue-700">
                            ₹{(review.cost - review.insuranceCovered).toLocaleString()}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          </div>

          {/* Sidebar */}
          <div className="lg:col-span-1">
            <div className="sticky top-6 space-y-4">
              {/* Location & Map */}
              {hospital.coordinates && (
                <motion.div
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="bg-white rounded-lg border border-gray-200 p-6"
                >
                  <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <MapPin className="w-5 h-5 text-blue-600" />
                    Location & Directions
                  </h3>
                  
                  {/* Map Container */}
                  <div className="h-64 rounded-lg overflow-hidden mb-3 border">
                    <HospitalMap
                      userLocation={userLocation || undefined}
                      hospitalLocation={hospital.coordinates}
                      hospitalName={hospital.name}
                    />
                  </div>
                  
                  {/* Distance Info */}
                  {hospital.distance && (
                    <div className="text-sm space-y-2 mb-3">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Distance:</span>
                        <span className="font-semibold">{hospital.distance.toFixed(1)} km</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Est. Time:</span>
                        <span className="font-semibold">{Math.ceil(hospital.distance / 0.5)} min</span>
                      </div>
                    </div>
                  )}
                  
                  <button 
                    onClick={() => {
                      // The map already shows the direction between two points!
                      // Just show a helpful message
                      alert(`The map above shows the route from your location to ${hospital.name}\n\nDistance: ${hospital.distance?.toFixed(1)} km\nEstimated Time: ${hospital.distance ? Math.ceil(hospital.distance / 0.5) : 'N/A'} min`);
                    }}
                    className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 transition-colors font-medium flex items-center justify-center gap-2"
                  >
                    <Navigation className="w-4 h-4" />
                    View Route Info
                  </button>
                </motion.div>
              )}

              {/* Insurance Accepted */}
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 }}
                className="bg-white rounded-lg border border-gray-200 p-6"
              >
                <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                  <Shield className="w-5 h-5 text-green-600" />
                  Insurance Accepted
                </h3>
                <div className="space-y-2">
                  {acceptedInsurance.length > 0 ? (
                    acceptedInsurance.map((insurance) => (
                      <div
                        key={insurance}
                        className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0"
                      >
                        <span className="text-sm text-gray-700">{insurance}</span>
                        <ChevronRight className="w-4 h-4 text-gray-400" />
                      </div>
                    ))
                  ) : (
                    <div className="text-sm text-gray-500">Loading insurance information...</div>
                  )}
                </div>
              </motion.div>

              {/* Quick Contact */}
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 }}
                className="bg-white rounded-lg border border-gray-200 p-6"
              >
                <h3 className="font-semibold text-gray-900 mb-3">Quick Contact</h3>
                <div className="space-y-3">
                  <div className="flex items-center gap-3 text-sm">
                    <Phone className="w-4 h-4 text-gray-600" />
                    <span className="text-gray-700">(555) 123-4567</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <Clock className="w-4 h-4 text-gray-600" />
                    <span className="text-gray-700">24/7 Emergency</span>
                  </div>
                </div>
              </motion.div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}