import { useState, useEffect } from "react"
import {
  Star,
  ChevronLeft,
  CheckCircle,
  DollarSign,
  Building2,
  Stethoscope,
  User
} from "lucide-react"
import { motion } from "motion/react"
import { submitReview } from "../../services/reviewApi"

const API_BASE_URL: string =
  (import.meta as any).env?.VITE_API_BASE_URL?.replace(/\/$/, "") ?? ""

interface DoctorItem {
  doctorId: string
  doctorName: string
}

interface Step4Props {
  data: {
    doctorId: string
    hospitalRating: number
    hospitalReview: string
    doctorRating: number
    doctorReview: string
    totalCost: number
    insuranceCovered: number
    doctorName: string
    surgeryType: string
    // Hospital ratings
    serviceRating: number
    maintenanceRating: number
    foodRating: number
    cleanlinessRating: number
    staffRating: number
    // Doctor ratings
    bedsideMannerRating: number
    expertiseRating: number
    communicationRating: number
    waitTimeRating: number
    thoroughnessRating: number
    followUpRating: number
  }
  onUpdate: (data: any) => void
  onBack: () => void
  allData: any
}

export function Step4ReviewSubmission({
  data,
  onUpdate,
  onBack,
  allData
}: Step4Props) {
  const [hospitalRating, setHospitalRating] = useState(data.hospitalRating || 0)
  const [hospitalReview, setHospitalReview] = useState(
    data.hospitalReview || ""
  )
  const [doctorRating, setDoctorRating] = useState(data.doctorRating || 0)
  const [doctorReview, setDoctorReview] = useState(data.doctorReview || "")
  const [totalCost, setTotalCost] = useState(data.totalCost || 0)
  const [insuranceCovered, setInsuranceCovered] = useState(
    data.insuranceCovered || 0
  )
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [reviewId, setReviewId] = useState("")

  // Doctor selection
  const [selectedDoctorId, setSelectedDoctorId] = useState(data.doctorId || "")
  const [doctors, setDoctors] = useState<DoctorItem[]>([])
  const [doctorsLoading, setDoctorsLoading] = useState(false)

  useEffect(() => {
    async function fetchDoctors() {
      setDoctorsLoading(true)
      try {
        const res = await fetch(`${API_BASE_URL}/doctors?limit=100`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const json = await res.json()
        const items: DoctorItem[] = Array.isArray(json)
          ? json
          : (json.items ?? [])
        setDoctors(items)
        // Auto-select if name matches extracted doctor name
        if (!selectedDoctorId && allData.doctorName) {
          const match = items.find((d) =>
            d.doctorName
              .toLowerCase()
              .includes(allData.doctorName.toLowerCase())
          )
          if (match) {
            setSelectedDoctorId(match.doctorId)
            onUpdate({ ...data, doctorId: match.doctorId })
          }
        }
      } catch (err) {
        console.error("[Doctors API]", err)
      } finally {
        setDoctorsLoading(false)
      }
    }
    fetchDoctors()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleDoctorChange = (doctorId: string) => {
    setSelectedDoctorId(doctorId)
    onUpdate({ ...data, doctorId })
  }

  // Hospital category ratings
  const [serviceRating, setServiceRating] = useState(data.serviceRating || 0)
  const [maintenanceRating, setMaintenanceRating] = useState(
    data.maintenanceRating || 0
  )
  const [foodRating, setFoodRating] = useState(data.foodRating || 0)
  const [cleanlinessRating, setCleanlinessRating] = useState(
    data.cleanlinessRating || 0
  )
  const [staffRating, setStaffRating] = useState(data.staffRating || 0)

  // Doctor category ratings
  const [bedsideMannerRating, setBedsideMannerRating] = useState(
    data.bedsideMannerRating || 0
  )
  const [expertiseRating, setExpertiseRating] = useState(
    data.expertiseRating || 0
  )
  const [communicationRating, setCommunicationRating] = useState(
    data.communicationRating || 0
  )
  const [waitTimeRating, setWaitTimeRating] = useState(data.waitTimeRating || 0)
  const [thoroughnessRating, setThoroughnessRating] = useState(
    data.thoroughnessRating || 0
  )
  const [followUpRating, setFollowUpRating] = useState(data.followUpRating || 0)

  const handleRatingClick = (type: "hospital" | "doctor", rating: number) => {
    if (type === "hospital") {
      setHospitalRating(rating)
      onUpdate({ ...data, hospitalRating: rating })
    } else {
      setDoctorRating(rating)
      onUpdate({ ...data, doctorRating: rating })
    }
  }

  const handleCategoryRating = (category: string, rating: number) => {
    const setters: any = {
      service: setServiceRating,
      maintenance: setMaintenanceRating,
      food: setFoodRating,
      cleanliness: setCleanlinessRating,
      staff: setStaffRating,
      bedsideManner: setBedsideMannerRating,
      expertise: setExpertiseRating,
      communication: setCommunicationRating,
      waitTime: setWaitTimeRating,
      thoroughness: setThoroughnessRating,
      followUp: setFollowUpRating
    }

    setters[category]?.(rating)
    onUpdate({ ...data, [`${category}Rating`]: rating })
  }

  const handleFieldUpdate = (field: string, value: any) => {
    const updates: any = { [field]: value }

    switch (field) {
      case "hospitalReview":
        setHospitalReview(value)
        break
      case "doctorReview":
        setDoctorReview(value)
        break
      case "totalCost":
        setTotalCost(Number(value))
        break
      case "insuranceCovered":
        setInsuranceCovered(Number(value))
        break
    }

    onUpdate({ ...data, ...updates })
  }

  const handleSubmit = async () => {
    setIsSubmitting(true)

    const completeReviewData = {
      ...allData,
      hospitalRating,
      hospitalReview,
      doctorRating,
      doctorReview,
      totalCost,
      insuranceCovered,
      outOfPocket: totalCost - insuranceCovered,
      // Hospital category ratings
      serviceRating,
      maintenanceRating,
      foodRating,
      cleanlinessRating,
      staffRating,
      // Doctor category ratings
      bedsideMannerRating,
      expertiseRating,
      communicationRating,
      waitTimeRating,
      thoroughnessRating,
      followUpRating
    }

    // -----------------------------------------------------------------------
    // Build the POST /reviews payload and submit
    // -----------------------------------------------------------------------
    setSubmitError(null)

    const payload = {
      hospitalId: allData.hospitalId,
      doctorId: selectedDoctorId,
      customerId: (window as any).__reviewCustomerId ?? "customer_unknown",
      purposeOfVisit:
        allData.surgeryType || allData.diagnosis || "Medical Visit",
      hospitalReview,
      doctorReview: { doctorId: selectedDoctorId, doctorReview },
      payment: allData.payment ?? {},
      documentIds: [
        ...(allData.documentIds ?? []),
        ...(allData.claimDocumentIds ?? [])
      ],
      claim: allData.hasInsurance ? (allData.claimData ?? null) : null,
      policyId: null,
      extractedData: {
        hospitalName: allData.hospitalName,
        doctorName: allData.doctorName,
        surgeryType: allData.surgeryType,
        procedureDate: allData.procedureDate,
        diagnosis: allData.diagnosis,
        medications: allData.medications
          ? allData.medications
              .split(",")
              .map((s: string) => s.trim())
              .filter(Boolean)
          : [],
        confidence: allData.extractedData?.confidence ?? 0.9
      },
      ratings: {
        hospital: {
          overall: hospitalRating,
          service: serviceRating,
          maintenance: maintenanceRating,
          food: foodRating,
          cleanliness: cleanlinessRating,
          staff: staffRating
        },
        doctor: {
          overall: doctorRating,
          bedsideManner: bedsideMannerRating,
          expertise: expertiseRating,
          communication: communicationRating,
          waitTime: waitTimeRating,
          thoroughness: thoroughnessRating,
          followUp: followUpRating
        }
      },
      totalCost,
      insuranceCovered,
      outOfPocket: totalCost - insuranceCovered
    }

    try {
      const result = await submitReview(payload)
      setReviewId(result.reviewId)
      setSubmitted(true)
    } catch (error: any) {
      console.error("Submission failed:", error)
      setSubmitError(error.message ?? "Submission failed. Please try again.")
    } finally {
      setIsSubmitting(false)
    }
  }

  const canSubmit =
    selectedDoctorId.length > 0 &&
    hospitalRating > 0 &&
    hospitalReview.trim().length > 20 &&
    doctorRating > 0 &&
    doctorReview.trim().length > 20 &&
    totalCost > 0 &&
    // All hospital categories must be rated
    serviceRating > 0 &&
    maintenanceRating > 0 &&
    foodRating > 0 &&
    cleanlinessRating > 0 &&
    staffRating > 0 &&
    // All doctor categories must be rated
    bedsideMannerRating > 0 &&
    expertiseRating > 0 &&
    communicationRating > 0 &&
    waitTimeRating > 0 &&
    thoroughnessRating > 0 &&
    followUpRating > 0

  // Helper component for category rating
  const CategoryRating = ({
    label,
    description,
    category,
    rating
  }: {
    label: string
    description: string
    category: string
    rating: number
  }) => (
    <div className="bg-gray-50 rounded-lg p-4">
      <div className="mb-2">
        <h4 className="text-sm font-semibold text-gray-900">{label}</h4>
        <p className="text-xs text-gray-600">{description}</p>
      </div>
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((r) => (
          <button
            key={r}
            onClick={() => handleCategoryRating(category, r)}
            className="focus:outline-none transition-transform hover:scale-110"
          >
            <Star
              className={`w-6 h-6 ${
                r <= rating
                  ? "fill-yellow-400 text-yellow-400"
                  : "text-gray-300"
              }`}
            />
          </button>
        ))}
        <span className="ml-2 text-sm font-semibold text-gray-900">
          {rating > 0 ? `${rating}.0` : "-"}
        </span>
      </div>
    </div>
  )

  if (submitted) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-2xl mx-auto"
      >
        <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
            className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6"
          >
            <CheckCircle className="w-12 h-12 text-green-600" />
          </motion.div>

          <h2 className="text-3xl font-bold text-gray-900 mb-3">
            Review Submitted Successfully!
          </h2>
          <p className="text-gray-600 mb-6">
            Thank you for sharing your experience. Your verified review will
            help others make informed healthcare decisions.
          </p>

          <div className="bg-blue-50 rounded-lg p-4 mb-6 inline-block">
            <p className="text-sm text-gray-600 mb-1">Review ID</p>
            <p className="font-mono text-blue-700 font-semibold">{reviewId}</p>
          </div>

          <div className="space-y-3">
            <a
              href="/"
              className="block w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors"
            >
              Back to Home
            </a>
            <a
              href="/past-reviews"
              className="block w-full border border-gray-300 py-3 rounded-lg font-medium hover:bg-gray-50 transition-colors"
            >
              View My Reviews
            </a>
          </div>

          <div className="mt-8 pt-6 border-t border-gray-200">
            <h3 className="font-semibold text-gray-900 mb-3">
              What happens next?
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="w-8 h-8 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mx-auto mb-2 font-bold">
                  1
                </div>
                <p className="font-medium text-gray-900 mb-1">AI Processing</p>
                <p className="text-gray-600">
                  Your review will be indexed for AI-powered search
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="w-8 h-8 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto mb-2 font-bold">
                  2
                </div>
                <p className="font-medium text-gray-900 mb-1">Verification</p>
                <p className="text-gray-600">
                  Documents verified and securely stored
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="w-8 h-8 bg-purple-100 text-purple-600 rounded-full flex items-center justify-center mx-auto mb-2 font-bold">
                  3
                </div>
                <p className="font-medium text-gray-900 mb-1">Published</p>
                <p className="text-gray-600">
                  Review goes live within 24 hours
                </p>
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-3xl mx-auto"
    >
      <div className="bg-white rounded-lg border border-gray-200 p-8">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            Share Your Experience
          </h2>
          <p className="text-gray-600">
            Rate and review the hospital and doctor
          </p>
        </div>

        <div className="space-y-8">
          {/* Doctor Selection */}
          <div className="pb-6 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <User className="w-5 h-5 text-purple-600" />
              Select Your Doctor *
            </h3>
            <select
              value={selectedDoctorId}
              onChange={(e) => handleDoctorChange(e.target.value)}
              disabled={doctorsLoading}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-60"
            >
              <option value="">
                {doctorsLoading
                  ? "Loading doctors…"
                  : "Select the doctor who treated you..."}
              </option>
              {doctors.map((d) => (
                <option key={d.doctorId} value={d.doctorId}>
                  {d.doctorName}
                </option>
              ))}
            </select>
            {allData.doctorName && !selectedDoctorId && (
              <p className="mt-1 text-xs text-gray-500">
                AI extracted doctor name:{" "}
                <span className="font-medium">{allData.doctorName}</span>
              </p>
            )}
          </div>

          {/* Hospital Review */}
          <div className="pb-6 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Building2 className="w-5 h-5 text-blue-600" />
              Hospital Review
            </h3>

            {/* Hospital Rating */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Overall Hospital Rating *
              </label>
              <div className="flex gap-2">
                {[1, 2, 3, 4, 5].map((rating) => (
                  <button
                    key={rating}
                    onClick={() => handleRatingClick("hospital", rating)}
                    className="focus:outline-none transition-transform hover:scale-110"
                  >
                    <Star
                      className={`w-10 h-10 ${
                        rating <= hospitalRating
                          ? "fill-yellow-400 text-yellow-400"
                          : "text-gray-300"
                      }`}
                    />
                  </button>
                ))}
                <span className="ml-3 text-2xl font-semibold text-gray-900">
                  {hospitalRating > 0 ? `${hospitalRating}.0` : "-"}
                </span>
              </div>
            </div>

            {/* Hospital Category Ratings */}
            <div className="mb-6">
              <h4 className="text-sm font-semibold text-gray-900 mb-3">
                Rate Specific Aspects *
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <CategoryRating
                  label="Service Quality"
                  description="Responsiveness, efficiency, patient care coordination"
                  category="service"
                  rating={serviceRating}
                />
                <CategoryRating
                  label="Maintenance"
                  description="Equipment condition, infrastructure, room facilities"
                  category="maintenance"
                  rating={maintenanceRating}
                />
                <CategoryRating
                  label="Food Quality"
                  description="Taste, variety, nutritional value, dietary accommodations"
                  category="food"
                  rating={foodRating}
                />
                <CategoryRating
                  label="Cleanliness"
                  description="Hygiene standards, room cleanliness, sanitation"
                  category="cleanliness"
                  rating={cleanlinessRating}
                />
                <CategoryRating
                  label="Staff Behavior"
                  description="Friendliness, professionalism, helpfulness"
                  category="staff"
                  rating={staffRating}
                />
              </div>
            </div>

            {/* Hospital Review Text */}
            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Write Your Review * (minimum 20 characters)
              </label>
              <textarea
                value={hospitalReview}
                onChange={(e) =>
                  handleFieldUpdate("hospitalReview", e.target.value)
                }
                placeholder="Share your experience at the hospital... How was the care? Staff? Facilities? What should others know?"
                rows={5}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              />
              <p className="text-xs text-gray-500 mt-1">
                {hospitalReview.length} characters (min 20 required)
              </p>
            </div>
          </div>

          {/* Doctor Review */}
          <div className="pb-6 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900 mb-1 flex items-center gap-2">
              <Stethoscope className="w-5 h-5 text-green-600" />
              Doctor Review - {allData.doctorName || "Unknown Doctor"}
            </h3>
            <p className="text-sm text-gray-600 mb-4">
              Based on extracted medical records for{" "}
              {allData.surgeryType || "procedure"}
            </p>

            {/* Doctor Rating */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Overall Doctor Rating *
              </label>
              <div className="flex gap-2">
                {[1, 2, 3, 4, 5].map((rating) => (
                  <button
                    key={rating}
                    onClick={() => handleRatingClick("doctor", rating)}
                    className="focus:outline-none transition-transform hover:scale-110"
                  >
                    <Star
                      className={`w-10 h-10 ${
                        rating <= doctorRating
                          ? "fill-yellow-400 text-yellow-400"
                          : "text-gray-300"
                      }`}
                    />
                  </button>
                ))}
                <span className="ml-3 text-2xl font-semibold text-gray-900">
                  {doctorRating > 0 ? `${doctorRating}.0` : "-"}
                </span>
              </div>
            </div>

            {/* Doctor Category Ratings */}
            <div className="mb-6">
              <h4 className="text-sm font-semibold text-gray-900 mb-3">
                Rate Specific Aspects *
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <CategoryRating
                  label="Bedside Manner"
                  description="Compassion, empathy, patient comfort, approachability"
                  category="bedsideManner"
                  rating={bedsideMannerRating}
                />
                <CategoryRating
                  label="Medical Expertise"
                  description="Knowledge, skill level, treatment accuracy, diagnosis"
                  category="expertise"
                  rating={expertiseRating}
                />
                <CategoryRating
                  label="Communication"
                  description="Explains clearly, listens to concerns, answers questions"
                  category="communication"
                  rating={communicationRating}
                />
                <CategoryRating
                  label="Wait Time"
                  description="Punctuality, appointment scheduling, minimal delays"
                  category="waitTime"
                  rating={waitTimeRating}
                />
                <CategoryRating
                  label="Thoroughness"
                  description="Detailed examination, attention to symptoms, diagnosis depth"
                  category="thoroughness"
                  rating={thoroughnessRating}
                />
                <CategoryRating
                  label="Follow-Up Care"
                  description="Post-treatment support, accessibility, ongoing monitoring"
                  category="followUp"
                  rating={followUpRating}
                />
              </div>
            </div>

            {/* Doctor Review Text */}
            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Write Your Review * (minimum 20 characters)
              </label>
              <textarea
                value={doctorReview}
                onChange={(e) =>
                  handleFieldUpdate("doctorReview", e.target.value)
                }
                placeholder="Share your experience with the doctor... How was their care? Communication? Expertise?"
                rows={5}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              />
              <p className="text-xs text-gray-500 mt-1">
                {doctorReview.length} characters (min 20 required)
              </p>
            </div>
          </div>

          {/* Cost Information */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-green-600" />
              Cost Breakdown
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-900 mb-2">
                  Total Cost * ($)
                </label>
                <input
                  type="number"
                  value={totalCost || ""}
                  onChange={(e) =>
                    handleFieldUpdate("totalCost", e.target.value)
                  }
                  placeholder="e.g., 15000"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-900 mb-2">
                  Insurance Covered ($)
                </label>
                <input
                  type="number"
                  value={insuranceCovered || ""}
                  onChange={(e) =>
                    handleFieldUpdate("insuranceCovered", e.target.value)
                  }
                  placeholder="e.g., 12000"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            {totalCost > 0 && (
              <div className="mt-4 bg-blue-50 rounded-lg p-4">
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <p className="text-xs text-gray-600 mb-1">Total Cost</p>
                    <p className="text-lg font-bold text-gray-900">
                      ${totalCost.toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-600 mb-1">
                      Insurance Covered
                    </p>
                    <p className="text-lg font-bold text-green-700">
                      ${insuranceCovered.toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-600 mb-1">Out of Pocket</p>
                    <p className="text-lg font-bold text-blue-700">
                      ${(totalCost - insuranceCovered).toLocaleString()}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Navigation Buttons */}
        <div className="flex justify-between gap-3 mt-8 pt-6 border-t border-gray-200">
          <button
            onClick={onBack}
            disabled={isSubmitting}
            className="px-6 py-3 rounded-lg font-medium border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <ChevronLeft className="w-4 h-4 inline mr-1" />
            Back
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || isSubmitting}
            className={`px-8 py-3 rounded-lg font-medium transition-colors ${
              canSubmit && !isSubmitting
                ? "bg-green-600 text-white hover:bg-green-700"
                : "bg-gray-200 text-gray-500 cursor-not-allowed"
            }`}
          >
            {isSubmitting ? (
              <span className="flex items-center gap-2">
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  className="w-5 h-5 border-2 border-white border-t-transparent rounded-full"
                />
                Submitting...
              </span>
            ) : (
              "Submit Review"
            )}
          </button>
          {submitError && (
            <p className="mt-3 text-sm text-red-600 text-center">
              {submitError}
            </p>
          )}
        </div>
      </div>
    </motion.div>
  )
}
