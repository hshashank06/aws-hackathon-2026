import { useState, useEffect } from "react"
import {
  Star,
  Calendar,
  DollarSign,
  FileCheck,
  Clock,
  AlertCircle,
  Loader2
} from "lucide-react"
import { motion } from "motion/react"
import { useAuth } from "../contexts/AuthContext"
import {
  getReviewsByCustomer,
  type CustomerReview
} from "../services/reviewApi"

function toNumber(val: number | string | undefined | null): number {
  if (val === undefined || val === null || val === "") return 0
  if (typeof val === "number") return isNaN(val) ? 0 : val
  // Strip currency symbols, commas, and whitespace before parsing
  const cleaned = String(val).replace(/[^0-9.\-]/g, "")
  const n = Number(cleaned)
  return isNaN(n) ? 0 : n
}

function formatDate(dateStr: string): string {
  const iso = dateStr?.slice(0, 10)
  if (!iso) return "—"
  return new Date(iso + "T12:00:00").toLocaleDateString()
}

export function PastReviews() {
  const { user } = useAuth()
  const [reviews, setReviews] = useState<CustomerReview[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!user?.userId) {
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)

    getReviewsByCustomer(user.userId)
      .then((items) => {
        const sorted = [...items].sort((a, b) =>
          (b.createdAt ?? "").localeCompare(a.createdAt ?? "")
        )
        setReviews(sorted)
      })
      .catch((err) => {
        console.error("[PastReviews] Failed to fetch reviews:", err)
        setError("Failed to load your reviews. Please try again later.")
      })
      .finally(() => setLoading(false))
  }, [user?.userId])

  return (
    <div className="min-h-full bg-gray-50 py-8">
      <div className="max-w-5xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Your Reviews
          </h1>
          <p className="text-gray-600 mb-8">
            Track your submitted reviews and their verification status
          </p>
        </motion.div>

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-16 gap-3 text-gray-500">
            <Loader2 className="w-6 h-6 animate-spin" />
            <span className="text-sm">Loading your reviews…</span>
          </div>
        )}

        {/* Error */}
        {!loading && error && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3"
          >
            <AlertCircle className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-red-700">{error}</p>
          </motion.div>
        )}

        {/* Reviews list */}
        {!loading && !error && (
          <div className="space-y-4">
            {reviews.map((review, index) => {
              const hospitalName =
                review.extractedData?.hospitalName || review.hospitalId
              const doctorName =
                review.extractedData?.doctorName || review.doctorId
              const treatment =
                review.extractedData?.surgeryType || review.purposeOfVisit
              const totalCost =
                toNumber(review.payment?.totalBillAmount) ||
                toNumber((review as any).totalCost)
              const insuranceCovered =
                toNumber(review.claim?.claimAmountApproved) ||
                toNumber((review as any).insuranceCovered)
              const doctorComment =
                typeof review.doctorReview === "object"
                  ? review.doctorReview?.doctorReview
                  : String(review.doctorReview ?? "")
              const comment = review.hospitalReview || doctorComment || ""
              const isPublished = review.verified === 1

              console.log(
                "REVIEW",
                review,
                "totalCost",
                totalCost,
                "insuranceCovered",
                insuranceCovered
              )

              return (
                <motion.div
                  key={review.reviewId}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.07 }}
                  className="bg-white rounded-lg shadow-sm border border-gray-200 p-6"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="font-semibold text-lg mb-1">
                        {hospitalName}
                      </h3>
                      <p className="text-sm text-gray-600">{doctorName}</p>
                    </div>
                    <span
                      className={`px-3 py-1 rounded-full text-xs font-medium flex items-center gap-1 ${
                        isPublished
                          ? "bg-green-100 text-green-700"
                          : "bg-yellow-100 text-yellow-700"
                      }`}
                    >
                      {isPublished ? (
                        <FileCheck className="w-3 h-3" />
                      ) : (
                        <Clock className="w-3 h-3" />
                      )}
                      {isPublished ? "Published" : "Pending"}
                    </span>
                  </div>

                  <div className="flex items-center gap-6 mb-4 text-sm">
                    <div className="flex items-center gap-1 text-gray-600">
                      <Calendar className="w-4 h-4" />
                      <span>{formatDate(review.createdAt)}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      {[...Array(5)].map((_, i) => (
                        <Star
                          key={i}
                          className={`w-4 h-4 ${
                            isPublished
                              ? "fill-yellow-400 text-yellow-400"
                              : i < 3
                                ? "fill-yellow-300 text-yellow-300"
                                : "text-gray-300"
                          }`}
                        />
                      ))}
                    </div>
                  </div>

                  <div className="bg-gray-50 rounded-lg p-4 mb-4">
                    <p className="text-sm font-medium text-gray-900 mb-2">
                      {treatment}
                    </p>
                    {comment && (
                      <p className="text-sm text-gray-600 italic">
                        "{comment}"
                      </p>
                    )}
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

            {reviews.length === 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center"
              >
                <Clock className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  No reviews yet
                </h3>
                <p className="text-gray-600 mb-4">
                  Start sharing your healthcare experiences to help others
                </p>
                <button className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors">
                  Create Your First Review
                </button>
              </motion.div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
