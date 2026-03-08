import { useState, useEffect } from "react"
import {
  Building2,
  AlertCircle,
  FileText,
  Mail,
  Calendar,
  CheckCircle2
} from "lucide-react"
import { motion } from "motion/react"
import { FileUploadWithVerification } from "../FileUploadWithVerification"
import { useAuth } from "../../contexts/AuthContext"

const API_BASE_URL: string =
  (import.meta as any).env?.VITE_API_BASE_URL?.replace(/\/$/, "") ?? ""

interface HospitalItem {
  hospitalId: string
  hospitalName: string
  address?: string
  location?: string
}

interface Step1Props {
  data: {
    hospitalId: string
    verificationFiles: File[]
    documentsVerified: boolean
  }
  onUpdate: (data: any) => void
  onNext: () => void
}

export function Step1HospitalSelection({ data, onUpdate, onNext }: Step1Props) {
  const { user } = useAuth()
  const [selectedHospital, setSelectedHospital] = useState(data.hospitalId)
  const [filesVerified, setFilesVerified] = useState(data.documentsVerified)
  const [hospitals, setHospitals] = useState<HospitalItem[]>([])
  const [hospitalsLoading, setHospitalsLoading] = useState(false)
  const [hospitalsError, setHospitalsError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchHospitals() {
      setHospitalsLoading(true)
      setHospitalsError(null)
      try {
        const res = await fetch(`${API_BASE_URL}/hospitals?limit=100`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const json = await res.json()
        // API returns { items: [...] } or array directly
        const items: HospitalItem[] = Array.isArray(json)
          ? json
          : (json.items ?? [])
        setHospitals(items)
      } catch (err: any) {
        setHospitalsError("Failed to load hospitals. Please try again.")
        console.error("[Hospitals API]", err)
      } finally {
        setHospitalsLoading(false)
      }
    }
    fetchHospitals()
  }, [])

  const handleHospitalChange = (hospitalId: string) => {
    setSelectedHospital(hospitalId)
    const selected = hospitals.find((h) => h.hospitalId === hospitalId)
    onUpdate({
      ...data,
      hospitalId,
      hospitalName: selected?.hospitalName ?? ""
    })
  }

  const handleVerificationComplete = (
    files: File[],
    allVerified: boolean,
    results: import("../../services/reviewApi").DocumentValidationResult[]
  ) => {
    setFilesVerified(allVerified)
    const documentIds = results
      .map((r) => r.documentId)
      .filter(Boolean) as string[]
    const payment = results.find((r) => r.payment)?.payment ?? null
    onUpdate({
      ...data,
      verificationFiles: files,
      documentsVerified: allVerified,
      documentIds,
      payment
    })
  }

  const canProceed =
    selectedHospital && data.verificationFiles.length > 0 && filesVerified

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-3xl mx-auto"
    >
      <div className="bg-white rounded-lg border border-gray-200 p-8">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            Hospital Selection & Verification
          </h2>
          <p className="text-gray-600">
            Select the hospital you visited and upload verification documents
          </p>
        </div>

        <div className="space-y-6">
          {/* Hospital Selection */}
          <div>
            <label className="block font-medium text-gray-900 mb-2">
              <Building2 className="w-5 h-5 inline mr-2" />
              Select Hospital
            </label>
            <select
              value={selectedHospital}
              onChange={(e) => handleHospitalChange(e.target.value)}
              disabled={hospitalsLoading}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-60"
            >
              <option value="">
                {hospitalsLoading
                  ? "Loading hospitals…"
                  : "Choose a hospital..."}
              </option>
              {hospitals.map((hospital) => (
                <option key={hospital.hospitalId} value={hospital.hospitalId}>
                  {hospital.hospitalName}
                  {hospital.address ? ` – ${hospital.address}` : ""}
                </option>
              ))}
            </select>
            {hospitalsError && (
              <p className="mt-1 text-sm text-red-600">{hospitalsError}</p>
            )}
          </div>

          {/* Detailed Document Requirements */}
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-200 p-6">
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5 text-blue-600" />
              What Documents Should You Upload?
            </h3>

            <div className="space-y-4">
              {/* Bills Section */}
              <div className="bg-white rounded-lg p-4 border border-blue-100">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <FileText className="w-4 h-4 text-blue-600" />
                  </div>
                  <div className="flex-1">
                    <h4 className="font-semibold text-gray-900 mb-2">
                      Hospital Bills & Invoices
                    </h4>
                    <ul className="text-sm text-gray-700 space-y-1">
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        <span>
                          <strong>Final hospital bill</strong> with itemized
                          charges (room, surgery, medications)
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        <span>
                          <strong>Payment receipts</strong> showing amount paid
                          (cash, card, or check)
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        <span>
                          <strong>Pharmacy bills</strong> for medications
                          prescribed during your stay
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        <span>
                          <strong>Lab test bills</strong> (blood work, X-rays,
                          MRI, CT scans)
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        <span>
                          <strong>Admission/Discharge summary</strong> with
                          billing code
                        </span>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Emails Section */}
              <div className="bg-white rounded-lg p-4 border border-blue-100">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Mail className="w-4 h-4 text-purple-600" />
                  </div>
                  <div className="flex-1">
                    <h4 className="font-semibold text-gray-900 mb-2">
                      Email Confirmations
                    </h4>
                    <ul className="text-sm text-gray-700 space-y-1">
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        <span>
                          <strong>Appointment confirmation emails</strong> from
                          hospital with date/time
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        <span>
                          <strong>Admission notification</strong> from hospital
                          administration
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        <span>
                          <strong>Online payment confirmation</strong> (if paid
                          via portal)
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        <span>
                          <strong>Discharge instructions</strong> sent via email
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        <span>
                          <strong>Follow-up appointment reminders</strong> from
                          hospital system
                        </span>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Appointments Section */}
              <div className="bg-white rounded-lg p-4 border border-blue-100">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Calendar className="w-4 h-4 text-green-600" />
                  </div>
                  <div className="flex-1">
                    <h4 className="font-semibold text-gray-900 mb-2">
                      Appointment Documents
                    </h4>
                    <ul className="text-sm text-gray-700 space-y-1">
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        <span>
                          <strong>Pre-admission appointment slip</strong> with
                          doctor's name and date
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        <span>
                          <strong>Surgery scheduling confirmation</strong> from
                          hospital coordinator
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        <span>
                          <strong>OPD (Outpatient Department) ticket</strong> or
                          registration slip
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        <span>
                          <strong>Doctor's referral letter</strong> or
                          consultation notes
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        <span>
                          <strong>Post-operative follow-up schedule</strong> or
                          appointment card
                        </span>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-4 bg-yellow-50 border border-yellow-200 rounded-lg p-3 flex gap-2">
              <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-yellow-900">
                <strong>Pro Tip:</strong> Upload at least 2-3 different types of
                documents for stronger verification. You can take photos of
                physical documents or upload PDFs/screenshots of emails.
              </p>
            </div>
          </div>

          {/* Document Upload */}
          <FileUploadWithVerification
            label="Upload Verification Documents"
            description="Drag and drop or click to upload bills, emails, or appointment confirmations"
            accept="image/*,.pdf"
            multiple={true}
            customerId={user?.userId ?? ""}
            onVerificationComplete={handleVerificationComplete}
          />

          {/* AI Verification Info Box */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex gap-3">
            <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-blue-900">
              <p className="font-medium mb-1">AI-Powered Verification</p>
              <p className="text-blue-800">
                Our AI system automatically verifies document authenticity and
                checks for tampering using advanced image recognition. This
                ensures all reviews on our platform are from real patients.
              </p>
            </div>
          </div>

          {/* Security Notice */}
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex gap-3">
            <div className="w-5 h-5 bg-green-600 rounded-full flex items-center justify-center flex-shrink-0">
              <svg
                className="w-3 h-3 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={3}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <div className="text-sm text-green-900">
              <p className="font-medium mb-1">Your Data is Safe</p>
              <p className="text-green-800">
                All documents are encrypted and stored securely. We never share
                your personal health information without your explicit consent.
              </p>
            </div>
          </div>
        </div>

        {/* Navigation Buttons */}
        <div className="flex justify-end gap-3 mt-8 pt-6 border-t border-gray-200">
          <button
            onClick={onNext}
            disabled={!canProceed}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              canProceed
                ? "bg-blue-600 text-white hover:bg-blue-700"
                : "bg-gray-200 text-gray-500 cursor-not-allowed"
            }`}
          >
            Continue to Insurance Details
          </button>
        </div>
      </div>
    </motion.div>
  )
}
