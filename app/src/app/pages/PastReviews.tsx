import { Star, Calendar, DollarSign, FileCheck, Clock } from "lucide-react";
import { motion } from "motion/react";

const mockReviews = [
  {
    id: "1",
    hospital: "City General Hospital",
    doctor: "Dr. Sarah Johnson",
    treatment: "Coronary Angioplasty",
    date: "2026-02-15",
    rating: 5,
    cost: 15000,
    insuranceCovered: 13500,
    status: "Published",
    comment: "Excellent care and transparent pricing. Dr. Johnson explained everything clearly.",
  },
  {
    id: "2",
    hospital: "St. Mary's Medical Center",
    doctor: "Dr. Emily Rodriguez",
    treatment: "Follow-up Consultation",
    date: "2026-01-20",
    rating: 4,
    cost: 200,
    insuranceCovered: 150,
    status: "Published",
    comment: "Good consultation, helpful advice for ongoing treatment.",
  },
  {
    id: "3",
    hospital: "Metropolitan Orthopedic Institute",
    doctor: "Dr. James Anderson",
    treatment: "Total Knee Replacement",
    date: "2025-12-10",
    rating: 5,
    cost: 22000,
    insuranceCovered: 18000,
    status: "Published",
    comment: "Life-changing surgery. Recovery was faster than expected.",
  },
];

export function PastReviews() {
  return (
    <div className="min-h-full bg-gray-50 py-8">
      <div className="max-w-5xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Your Reviews</h1>
          <p className="text-gray-600 mb-8">
            Track your submitted reviews and their verification status
          </p>
        </motion.div>

        <div className="space-y-4">
          {mockReviews.map((review, index) => (
            <motion.div
              key={review.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className="bg-white rounded-lg shadow-sm border border-gray-200 p-6"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-lg mb-1">{review.hospital}</h3>
                  <p className="text-sm text-gray-600">{review.doctor}</p>
                </div>
                <span className="bg-green-100 text-green-700 px-3 py-1 rounded-full text-xs font-medium flex items-center gap-1">
                  <FileCheck className="w-3 h-3" />
                  {review.status}
                </span>
              </div>

              <div className="flex items-center gap-6 mb-4 text-sm">
                <div className="flex items-center gap-1 text-gray-600">
                  <Calendar className="w-4 h-4" />
                  <span>{new Date(review.date).toLocaleDateString()}</span>
                </div>
                <div className="flex items-center gap-1">
                  {[...Array(5)].map((_, i) => (
                    <Star
                      key={i}
                      className={`w-4 h-4 ${
                        i < review.rating
                          ? "fill-yellow-400 text-yellow-400"
                          : "text-gray-300"
                      }`}
                    />
                  ))}
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-4 mb-4">
                <p className="text-sm font-medium text-gray-900 mb-2">{review.treatment}</p>
                <p className="text-sm text-gray-600 italic">"{review.comment}"</p>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div className="bg-blue-50 rounded-lg p-3">
                  <div className="flex items-center gap-1 text-blue-700 text-xs font-medium mb-1">
                    <DollarSign className="w-3 h-3" />
                    <span>Total Cost</span>
                  </div>
                  <p className="text-sm font-semibold">₹{review.cost.toLocaleString()}</p>
                </div>
                <div className="bg-green-50 rounded-lg p-3">
                  <div className="flex items-center gap-1 text-green-700 text-xs font-medium mb-1">
                    <DollarSign className="w-3 h-3" />
                    <span>Insurance Covered</span>
                  </div>
                  <p className="text-sm font-semibold">₹{review.insuranceCovered.toLocaleString()}</p>
                </div>
                <div className="bg-purple-50 rounded-lg p-3">
                  <div className="flex items-center gap-1 text-purple-700 text-xs font-medium mb-1">
                    <DollarSign className="w-3 h-3" />
                    <span>Out of Pocket</span>
                  </div>
                  <p className="text-sm font-semibold">
                    ₹{(review.cost - review.insuranceCovered).toLocaleString()}
                  </p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {mockReviews.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center"
          >
            <Clock className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">No reviews yet</h3>
            <p className="text-gray-600 mb-4">
              Start sharing your healthcare experiences to help others
            </p>
            <button className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors">
              Create Your First Review
            </button>
          </motion.div>
        )}
      </div>
    </div>
  );
}
