import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { MapPin, DollarSign, Shield, ChevronRight, CheckCircle, ChevronDown, ChevronUp, Star, Navigation } from "lucide-react";
import { Hospital } from "../data/mockData";
import ReactMarkdown from "react-markdown";

interface HospitalCardProps {
  hospital: Hospital;
}

export function HospitalCard({ hospital }: HospitalCardProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [showFullDescription, setShowFullDescription] = useState(false);

  const handleMouseEnter = () => {
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
  };

  // Use insuranceCoveragePercent from Lambda if available, otherwise calculate from reviews
  const insuranceCoveragePercent = hospital.insuranceCoveragePercent !== undefined
    ? hospital.insuranceCoveragePercent
    : (() => {
        const totalCost = hospital.reviews.reduce((acc, r) => acc + r.cost, 0);
        const totalInsurance = hospital.reviews.reduce((acc, r) => acc + r.insuranceCovered, 0);
        return totalCost > 0 ? Math.round((totalInsurance / totalCost) * 100) : 85;
      })();

  // Trust badge color mapping
  const badgeColors = {
    platinum: "bg-purple-100 text-purple-700 border-purple-300",
    gold: "bg-yellow-100 text-yellow-700 border-yellow-300",
    silver: "bg-gray-100 text-gray-700 border-gray-300",
    bronze: "bg-orange-100 text-orange-700 border-orange-300",
  };

  // Truncate description to first 2-3 paragraphs or 4 sentences
  const truncateDescription = (text: string) => {
    if (!text) return "";
    
    const cleanText = text.trim();
    if (!cleanText) return "";
    
    // For Markdown content, split by double newlines (paragraphs)
    const paragraphs = cleanText.split(/\n\n+/).filter(p => p.trim());
    
    // If we have multiple paragraphs, take first 2-3 paragraphs
    if (paragraphs.length > 3) {
      return paragraphs.slice(0, 2).join("\n\n");
    }
    
    // If we have 2-3 paragraphs, return them all
    if (paragraphs.length >= 2) {
      return cleanText;
    }
    
    // Otherwise, split by sentences (for single paragraph content)
    const sentences = cleanText.match(/[^.!?]+[.!?]+/g);
    
    if (!sentences || sentences.length <= 4) {
      return cleanText;
    }
    
    return sentences.slice(0, 4).join(" ");
  };

  const fullDescription = hospital.description || "";
  const truncatedDescription = truncateDescription(fullDescription);
  const hasMoreContent = fullDescription.trim().length > truncatedDescription.length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`bg-white rounded-lg border-2 transition-all relative ${
        isHovered ? "border-blue-500 shadow-lg" : "border-gray-200 shadow-sm"
      }`}
    >
      {/* Distance Badge - Top Right */}
      {hospital.distance != null && (
        <div className="absolute top-4 right-4 bg-blue-600 text-white px-3 py-1.5 rounded-full text-sm font-medium flex items-center gap-1 shadow-md">
          <Navigation className="w-3.5 h-3.5" />
          {hospital.distance.toFixed(1)} km
        </div>
      )}
      
      <div className="p-6">
        {/* Header Section */}
        <Link to={`/hospital/${hospital.id}`} className="block">
          <div className="flex gap-4 mb-4">
            <img
              src={hospital.imageUrl}
              alt={hospital.name}
              className="w-16 h-16 rounded-lg object-cover bg-gray-100"
              onError={(e) => {
                // Fallback to default image if loading fails
                e.currentTarget.src = "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=400";
              }}
            />
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-semibold text-lg">{hospital.name}</h3>
                {hospital.verificationBadge && (
                  <span className={`px-2 py-0.5 rounded text-xs font-medium border ${
                    badgeColors[hospital.verificationBadge as keyof typeof badgeColors] || badgeColors.bronze
                  }`}>
                    {hospital.verificationBadge.toUpperCase()}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1 text-sm text-gray-600 mb-2">
                <MapPin className="w-4 h-4" />
                <span>{hospital.location}</span>
              </div>
              <div className="flex items-center gap-4 text-sm">
                <div className="flex items-center gap-1">
                  <Star className="w-4 h-4 fill-yellow-400 text-yellow-400" />
                  <span className="font-medium">{hospital.rating.toFixed(1)}</span>
                  <span className="text-gray-500">({hospital.reviewCount} reviews)</span>
                </div>
                {hospital.trustScore && (
                  <div className="flex items-center gap-1 text-green-600">
                    <CheckCircle className="w-4 h-4" />
                    <span className="font-medium">Trust: {hospital.trustScore}%</span>
                  </div>
                )}
              </div>
            </div>
            <ChevronRight className={`w-5 h-5 text-gray-400 transition-transform ${isHovered ? "translate-x-1" : ""}`} />
          </div>
        </Link>

        {/* Description with Read More */}
        {fullDescription && fullDescription.trim() && (
          <div className="text-sm text-gray-600 mb-4">
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown>
                {showFullDescription ? fullDescription : (truncatedDescription + (hasMoreContent ? "..." : ""))}
              </ReactMarkdown>
            </div>
            {hasMoreContent && (
              <button
                onClick={(e) => {
                  e.preventDefault();
                  setShowFullDescription(!showFullDescription);
                }}
                className="text-blue-600 hover:text-blue-700 font-medium mt-1 flex items-center gap-1 text-xs"
              >
                {showFullDescription ? (
                  <>
                    Show less <ChevronUp className="w-3 h-3" />
                  </>
                ) : (
                  <>
                    Read more <ChevronDown className="w-3 h-3" />
                  </>
                )}
              </button>
            )}
          </div>
        )}

        <Link to={`/hospital/${hospital.id}`} className="block">
          {/* Key Stats */}
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="bg-blue-50 rounded-lg p-3">
              <div className="flex items-center gap-1 text-blue-700 text-xs font-medium mb-1">
                <DollarSign className="w-3 h-3" />
                <span>Avg. Cost Range</span>
              </div>
              <p className="text-sm font-semibold">
                ₹{(hospital.avgCostRange.min / 1000).toFixed(0)}k - ₹{(hospital.avgCostRange.max / 1000).toFixed(0)}k
              </p>
            </div>
            <div className="bg-green-50 rounded-lg p-3">
              <div className="flex items-center gap-1 text-green-700 text-xs font-medium mb-1">
                <Shield className="w-3 h-3" />
                <span>Insurance Coverage</span>
              </div>
              <p className="text-sm font-semibold">~{insuranceCoveragePercent}%</p>
            </div>
            <div className="bg-purple-50 rounded-lg p-3">
              <div className="text-purple-700 text-xs font-medium mb-1">
                Specialties
              </div>
              <p className="text-sm font-semibold">{hospital.specialties.length}</p>
            </div>
          </div>

          {/* Specialties Tags */}
          <div className="flex flex-wrap gap-2 mb-4">
            {hospital.specialties.slice(0, 4).map((specialty) => (
              <span
                key={specialty}
                className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded-full"
              >
                {specialty}
              </span>
            ))}
          </div>

          {/* AI Recommendation */}
          {hospital.aiRecommendation && (
            <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-4 border border-blue-100">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-6 h-6 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-xs font-bold">AI</span>
                </div>
                <span className="text-sm font-semibold text-gray-700">
                  Why this matches your needs
                </span>
              </div>
              <div className="prose prose-sm max-w-none text-gray-600">
                <ReactMarkdown>{hospital.aiRecommendation}</ReactMarkdown>
              </div>
            </div>
          )}

          {/* Reviews Summary */}
          {hospital.reviews && hospital.reviews.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <h4 className="text-sm font-semibold mb-2">Recent Patient Reviews</h4>
              <div className="space-y-2">
                {hospital.reviews.slice(0, 2).map((review) => (
                  <div key={review.id} className="bg-gray-50 rounded p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-medium">{review.patientName}</span>
                      {review.verified && (
                        <span className="flex items-center gap-0.5 text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">
                          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                          </svg>
                          Verified
                        </span>
                      )}
                      {review.date && (
                        <span className="text-xs text-gray-500 ml-auto">{review.date}</span>
                      )}
                    </div>
                    <p className="text-xs text-gray-600 mb-1">{review.treatment}</p>
                    <div className="text-xs text-gray-600 line-clamp-2 prose prose-xs max-w-none [&>h1]:text-sm [&>h1]:font-semibold [&>h1]:mb-1 [&>h2]:text-xs [&>h2]:font-semibold [&>h2]:mb-1 [&>h3]:text-xs [&>h3]:font-medium [&>h3]:mb-1 [&>p]:text-xs [&>p]:mb-1">
                      <ReactMarkdown>{review.comment}</ReactMarkdown>
                    </div>
                    {(review.cost > 0 || review.insuranceCovered > 0) && (
                      <div className="flex gap-2 mt-2">
                        {review.cost > 0 && (
                          <div className="bg-blue-50 text-blue-700 px-2 py-1 rounded text-xs">
                            <span className="font-medium">Cost: ₹{review.cost.toLocaleString()}</span>
                          </div>
                        )}
                        {review.insuranceCovered > 0 && (
                          <div className="bg-green-50 text-green-700 px-2 py-1 rounded text-xs">
                            <span className="font-medium">Covered: ₹{review.insuranceCovered.toLocaleString()}</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </Link>
      </div>
    </motion.div>
  );
}
