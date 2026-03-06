import { motion } from "motion/react";
import { Star, GraduationCap, Briefcase } from "lucide-react";
import { Doctor } from "../data/mockData";
import ReactMarkdown from "react-markdown";

interface DoctorCardProps {
  doctor: Doctor;
  index: number;
}

export function DoctorCard({ doctor, index }: DoctorCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1 }}
      className="bg-white rounded-lg border border-gray-200 shadow-sm p-4 hover:shadow-md transition-shadow"
    >
      {/* Header */}
      <div className="flex gap-3 mb-3">
        <img
          src={doctor.imageUrl}
          alt={doctor.name}
          className="w-12 h-12 rounded-full object-cover"
        />
        <div className="flex-1">
          <h4 className="font-semibold text-sm mb-0.5">{doctor.name}</h4>
          <p className="text-xs text-gray-600">{doctor.specialty}</p>
          <div className="flex items-center gap-1 mt-1">
            <Star className="w-3 h-3 fill-yellow-400 text-yellow-400" />
            <span className="text-xs font-medium">{doctor.rating}</span>
            {doctor.reviewCount > 0 && (
              <span className="text-xs text-gray-500">({doctor.reviewCount})</span>
            )}
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 gap-2 mb-3">
        <div className="flex items-center gap-1.5 text-xs">
          <Briefcase className="w-3 h-3 text-blue-600" />
          <span className="text-gray-600">{doctor.experience} years exp.</span>
        </div>
      </div>

      {/* Qualifications */}
      <div className="mb-3">
        <div className="flex items-center gap-1 mb-1">
          <GraduationCap className="w-3 h-3 text-gray-600" />
          <span className="text-xs font-medium text-gray-700">Qualifications</span>
        </div>
        <div className="flex flex-wrap gap-1">
          {doctor.qualifications && doctor.qualifications.length > 0 ? (
            doctor.qualifications.map((qual) => (
              <span key={qual} className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded font-medium">
                {qual}
              </span>
            ))
          ) : (
            <span className="text-xs text-gray-500">No qualifications listed</span>
          )}
        </div>
      </div>

      {/* AI Summary */}
      <div className="bg-gradient-to-r from-green-50 to-blue-50 rounded p-3 border border-green-100">
        <div className="flex items-center gap-1.5 mb-2">
          <div className="w-5 h-5 bg-gradient-to-r from-green-500 to-blue-500 rounded-full flex items-center justify-center">
            <span className="text-white text-[10px] font-bold">AI</span>
          </div>
          <span className="text-xs font-semibold text-gray-700">Why this doctor</span>
        </div>
        <div className="prose prose-xs max-w-none text-gray-600 text-xs">
          <ReactMarkdown>{doctor.aiSummary}</ReactMarkdown>
        </div>
      </div>

      {/* Patient Reviews Summary */}
      {doctor.reviews.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <h5 className="text-xs font-semibold mb-2">Patient Feedback</h5>
          <div className="space-y-2">
            {doctor.reviews.slice(0, 1).map((review) => (
              <div key={review.id} className="bg-gray-50 rounded p-2">
                <div className="flex items-center gap-1 mb-1">
                  <div className="flex">
                    {[...Array(5)].map((_, i) => (
                      <Star
                        key={i}
                        className={`w-2.5 h-2.5 ${
                          i < review.rating
                            ? "fill-yellow-400 text-yellow-400"
                            : "text-gray-300"
                        }`}
                      />
                    ))}
                  </div>
                  <span className="text-[10px] font-medium">{review.patientName}</span>
                  {review.verified && (
                    <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded">
                      ✓
                    </span>
                  )}
                </div>
                <p className="text-[10px] text-gray-500 line-clamp-2">{review.comment}</p>
                <div className="flex gap-2 mt-1 text-[10px] text-gray-600">
                  <span>Cost: ${review.cost.toLocaleString()}</span>
                  <span>•</span>
                  <span>Covered: ${review.insuranceCovered.toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
