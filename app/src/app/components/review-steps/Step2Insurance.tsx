import { useState, useEffect } from "react"
import {
  Shield,
  ChevronLeft,
  FileText,
  Mail,
  Smartphone,
  CheckCircle2,
  Image,
  AlertTriangle
} from "lucide-react"
import { motion } from "motion/react"
import { FileUploadWithVerification } from "../FileUploadWithVerification"
import { validateInsuranceClaim } from "../../services/reviewApi"
import type { DocumentValidationResult } from "../../services/reviewApi"
import { useAuth } from "../../contexts/AuthContext"

const API_BASE_URL: string =
  (import.meta as any).env?.VITE_API_BASE_URL?.replace(/\/$/, "") ?? ""

interface InsuranceCompanyItem {
  insuranceCompanyId: string
  insuranceCompanyName: string
}

interface Step2Props {
  data: {
    hasInsurance: boolean
    insuranceCompanyId: string
    claimFiles: File[]
    claimVerified: boolean
  }
  onUpdate: (data: any) => void
  onNext: () => void
  onBack: () => void
}

export function Step2Insurance({ data, onUpdate, onNext, onBack }: Step2Props) {
  const { user } = useAuth()
  const [hasInsurance, setHasInsurance] = useState(data.hasInsurance)
  const [insuranceCompanyId, setInsuranceCompanyId] = useState(
    data.insuranceCompanyId
  )
  const [claimVerified, setClaimVerified] = useState(data.claimVerified)
  const [companies, setCompanies] = useState<InsuranceCompanyItem[]>([])
  const [companiesLoading, setCompaniesLoading] = useState(false)

  useEffect(() => {
    async function fetchCompanies() {
      setCompaniesLoading(true)
      try {
        const res = await fetch(`${API_BASE_URL}/insurance-companies?limit=100`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const json = await res.json()
        const items: InsuranceCompanyItem[] = Array.isArray(json)
          ? json
          : (json.items ?? [])
        setCompanies(items)
      } catch (err) {
        console.error("[Insurance Companies API]", err)
      } finally {
        setCompaniesLoading(false)
      }
    }
    fetchCompanies()
  }, [])

  const handleInsuranceToggle = (value: boolean) => {
    setHasInsurance(value)
    onUpdate({
      ...data,
      hasInsurance: value,
      insuranceCompanyId: value ? data.insuranceCompanyId : "",
      claimFiles: value ? data.claimFiles : [],
      claimVerified: value ? data.claimVerified : true,
      claimData: value ? (data as any).claimData : null
    })
  }

  const handleInsuranceCompanyChange = (id: string) => {
    setInsuranceCompanyId(id)
    onUpdate({ ...data, insuranceCompanyId: id })
  }

  const handleClaimVerification = (
    files: File[],
    allVerified: boolean,
    results: DocumentValidationResult[]
  ) => {
    setClaimVerified(allVerified)
    const claimData = results.find((r) => r.claimData)?.claimData ?? null
    const claimDocumentIds = results
      .map((r) => r.documentId)
      .filter(Boolean) as string[]
    onUpdate({
      ...data,
      claimFiles: files,
      claimVerified: allVerified,
      claimData,
      claimDocumentIds
    })
  }

  const canProceed =
    !hasInsurance ||
    (insuranceCompanyId && data.claimFiles.length > 0 && claimVerified)

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-3xl mx-auto"
    >
      <div className="bg-white rounded-lg border border-gray-200 p-8">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            Insurance Information (Optional)
          </h2>
          <p className="text-gray-600">
            Help others understand insurance coverage and claim outcomes
          </p>
        </div>

        <div className="space-y-6">
          {/* Insurance Toggle */}
          <div className="bg-gray-50 rounded-lg p-6 border border-gray-200">
            <label className="block font-medium text-gray-900 mb-4">
              Did you use insurance for this visit?
            </label>
            <div className="flex gap-4">
              <button
                onClick={() => handleInsuranceToggle(true)}
                className={`flex-1 py-3 px-4 rounded-lg border-2 font-medium transition-all ${
                  hasInsurance
                    ? "border-blue-600 bg-blue-50 text-blue-700"
                    : "border-gray-300 bg-white text-gray-700 hover:border-gray-400"
                }`}
              >
                <Shield className="w-5 h-5 inline mr-2" />
                Yes, I had insurance
              </button>
              <button
                onClick={() => handleInsuranceToggle(false)}
                className={`flex-1 py-3 px-4 rounded-lg border-2 font-medium transition-all ${
                  !hasInsurance
                    ? "border-blue-600 bg-blue-50 text-blue-700"
                    : "border-gray-300 bg-white text-gray-700 hover:border-gray-400"
                }`}
              >
                No, I paid out-of-pocket
              </button>
            </div>
          </div>

          {/* Insurance Details (shown only if hasInsurance is true) */}
          {hasInsurance && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="space-y-6"
            >
              {/* Insurance Company Selection */}
              <div>
                <label className="block font-medium text-gray-900 mb-2">
                  Select Insurance Company
                </label>
                <select
                  value={insuranceCompanyId}
                  onChange={(e) => handleInsuranceCompanyChange(e.target.value)}
                  disabled={companiesLoading}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-60"
                >
                  <option value="">
                    {companiesLoading
                      ? "Loading companies…"
                      : "Choose your insurance provider..."}
                  </option>
                  {companies.map((c) => (
                    <option
                      key={c.insuranceCompanyId}
                      value={c.insuranceCompanyId}
                    >
                      {c.insuranceCompanyName}
                    </option>
                  ))}
                </select>
              </div>

              {/* Detailed Insurance Document Requirements */}
              <div className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg border border-purple-200 p-6">
                <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Shield className="w-5 h-5 text-purple-600" />
                  What Insurance Documents Should You Upload?
                </h3>

                <div className="space-y-4">
                  {/* Claims Screenshots Section */}
                  <div className="bg-white rounded-lg p-4 border border-purple-100">
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <Image className="w-4 h-4 text-blue-600" />
                      </div>
                      <div className="flex-1">
                        <h4 className="font-semibold text-gray-900 mb-2">
                          Insurance Portal Screenshots
                        </h4>
                        <ul className="text-sm text-gray-700 space-y-1">
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Claim status page</strong> showing
                              "Approved" or "Processed" status
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Claim details screen</strong> with claim
                              number, date filed, and amounts
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>EOB (Explanation of Benefits)</strong>{" "}
                              from insurer's portal or app
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Payment breakdown</strong> showing covered
                              vs. out-of-pocket amounts
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Mobile app screenshots</strong> of claim
                              history and payment records
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Pre-authorization approval</strong> screen
                              (if surgery required prior approval)
                            </span>
                          </li>
                        </ul>
                      </div>
                    </div>
                  </div>

                  {/* Emails Section */}
                  <div className="bg-white rounded-lg p-4 border border-purple-100">
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <Mail className="w-4 h-4 text-green-600" />
                      </div>
                      <div className="flex-1">
                        <h4 className="font-semibold text-gray-900 mb-2">
                          Insurance Emails & Letters
                        </h4>
                        <ul className="text-sm text-gray-700 space-y-1">
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Claim approval email</strong> from your
                              insurance company
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>EOB email attachment</strong> (PDF) sent
                              by insurer after processing
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Pre-authorization approval letter</strong>{" "}
                              for scheduled procedures
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Payment confirmation email</strong>{" "}
                              showing reimbursement amount
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Claim submission confirmation</strong>{" "}
                              with reference number
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Coverage verification letter</strong> from
                              insurance provider
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Denial letter</strong> (if applicable)
                              explaining rejected claims
                            </span>
                          </li>
                        </ul>
                      </div>
                    </div>
                  </div>

                  {/* SMS/Messages Section */}
                  <div className="bg-white rounded-lg p-4 border border-purple-100">
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <Smartphone className="w-4 h-4 text-purple-600" />
                      </div>
                      <div className="flex-1">
                        <h4 className="font-semibold text-gray-900 mb-2">
                          SMS & Text Messages
                        </h4>
                        <ul className="text-sm text-gray-700 space-y-1">
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Claim status update texts</strong> from
                              insurance company's SMS service
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Payment processed notifications</strong>{" "}
                              via SMS with transaction ID
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Pre-authorization approval texts</strong>{" "}
                              with approval code
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Claim settlement messages</strong> with
                              payment timeline
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>WhatsApp/Telegram messages</strong> from
                              insurance customer service
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Screenshots of claim tracking</strong>{" "}
                              from insurance chatbot or support
                            </span>
                          </li>
                        </ul>
                      </div>
                    </div>
                  </div>

                  {/* Physical Documents */}
                  <div className="bg-white rounded-lg p-4 border border-purple-100">
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <FileText className="w-4 h-4 text-orange-600" />
                      </div>
                      <div className="flex-1">
                        <h4 className="font-semibold text-gray-900 mb-2">
                          Physical Insurance Documents
                        </h4>
                        <ul className="text-sm text-gray-700 space-y-1">
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Physical EOB letter</strong> mailed by
                              insurance company
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Reimbursement check</strong> or bank
                              deposit slip from insurer
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Insurance card copy</strong> showing
                              active coverage (redact sensitive info)
                            </span>
                          </li>
                          <li className="flex items-start gap-2">
                            <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                            <span>
                              <strong>Cashless treatment approval form</strong>{" "}
                              from TPA (Third Party Administrator)
                            </span>
                          </li>
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-4 bg-yellow-50 border border-yellow-200 rounded-lg p-3 flex gap-2">
                  <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-yellow-900">
                    <strong>Pro Tip:</strong> Upload multiple document types for
                    stronger verification. You can redact personal identifiers
                    like policy numbers or Aadhar/SSN before uploading.
                  </p>
                </div>
              </div>

              {/* Claim Documents Upload */}
              <FileUploadWithVerification
                label="Upload Insurance Claim Documents"
                description="Upload screenshots, emails, SMS, or documents proving your insurance claim"
                accept="image/*,.pdf"
                multiple={true}
                customerId={user?.userId ?? ""}
                validateFn={validateInsuranceClaim}
                onVerificationComplete={handleClaimVerification}
              />

              {/* Privacy Disclaimer */}
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex gap-3">
                <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-yellow-900">
                  <p className="font-medium mb-1">Your Choice, Your Privacy</p>
                  <p className="text-yellow-800">
                    Sharing insurance information is completely optional. We
                    encrypt all documents end-to-end and only use them to verify
                    your review. Personal identifiers are redacted before any
                    data is displayed publicly. You can help others make
                    informed decisions about insurance coverage without
                    compromising your privacy.
                  </p>
                </div>
              </div>

              {/* AI Tampering Detection Info */}
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 flex gap-3">
                <div className="w-5 h-5 bg-purple-600 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-white text-xs font-bold">AI</span>
                </div>
                <div className="text-sm text-purple-900">
                  <p className="font-medium mb-1">AI Tampering Detection</p>
                  <p className="text-purple-800">
                    Our AI analyzes claim documents for authenticity, checking
                    metadata, image manipulation, and consistency with known
                    insurance formats. This protects the integrity of our
                    platform.
                  </p>
                </div>
              </div>
            </motion.div>
          )}
        </div>

        {/* Navigation Buttons */}
        <div className="flex justify-between gap-3 mt-8 pt-6 border-t border-gray-200">
          <button
            onClick={onBack}
            className="px-6 py-3 rounded-lg font-medium border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <ChevronLeft className="w-4 h-4 inline mr-1" />
            Back
          </button>
          <button
            onClick={onNext}
            disabled={!canProceed}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              canProceed
                ? "bg-blue-600 text-white hover:bg-blue-700"
                : "bg-gray-200 text-gray-500 cursor-not-allowed"
            }`}
          >
            Continue to Medical Records
          </button>
        </div>
      </div>
    </motion.div>
  )
}
