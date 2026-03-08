import { useState } from "react"
import { FileText, ChevronLeft, Loader, Sparkles, X } from "lucide-react"
import { motion, AnimatePresence } from "motion/react"
import {
  extractMedicalData,
  ExtractedMedicalData
} from "../../services/reviewApi"
import { useAuth } from "../../contexts/AuthContext"

interface Step3Props {
  data: {
    medicalRecordFiles: File[]
    medicalRecordDocumentIds: string[]
    extractedData: ExtractedMedicalData | null
    surgeryType: string
    hospitalName: string
    doctorName: string
    diagnosis: string
    medications: string
    procedureDate: string
  }
  onUpdate: (data: any) => void
  onNext: () => void
  onBack: () => void
}

export function Step3MedicalRecords({
  data,
  onUpdate,
  onNext,
  onBack
}: Step3Props) {
  const { user } = useAuth()
  const [files, setFiles] = useState<File[]>(data.medicalRecordFiles)
  const [isExtracting, setIsExtracting] = useState(false)
  const [extractedData, setExtractedData] =
    useState<ExtractedMedicalData | null>(data.extractedData)

  // Form fields
  const [surgeryType, setSurgeryType] = useState(data.surgeryType)
  const [hospitalName, setHospitalName] = useState(data.hospitalName)
  const [doctorName, setDoctorName] = useState(data.doctorName)
  const [diagnosis, setDiagnosis] = useState(data.diagnosis)
  const [medications, setMedications] = useState(data.medications)
  const [procedureDate, setProcedureDate] = useState(data.procedureDate)

  const removeFile = (index: number) => {
    const updated = files.filter((_, i) => i !== index)
    setFiles(updated)
    if (updated.length === 0) {
      setExtractedData(null)
    }
    onUpdate({
      ...data,
      medicalRecordFiles: updated,
      extractedData: updated.length === 0 ? null : data.extractedData
    })
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return
    
    if (!user?.userId) {
      alert("Authentication required. Please sign in and try again.")
      return
    }

    const uploadedFiles = Array.from(e.target.files)
    setFiles(uploadedFiles)
    setIsExtracting(true)

    try {
      // Call AI extraction API
      const {
        extractedData: extracted,
        documentIds: medicalRecordDocumentIds
      } = await extractMedicalData(uploadedFiles, user.userId)
      setExtractedData(extracted)

      // Auto-fill form fields
      setSurgeryType(extracted.surgeryType)
      setHospitalName(extracted.hospitalName)
      setDoctorName(extracted.doctorName)
      setDiagnosis(extracted.diagnosis)
      setMedications(extracted.medications.join(", "))
      setProcedureDate(extracted.procedureDate)

      onUpdate({
        medicalRecordFiles: uploadedFiles,
        medicalRecordDocumentIds,
        extractedData: extracted,
        surgeryType: extracted.surgeryType,
        hospitalName: extracted.hospitalName,
        doctorName: extracted.doctorName,
        diagnosis: extracted.diagnosis,
        medications: extracted.medications.join(", "),
        procedureDate: extracted.procedureDate
      })
    } catch (error) {
      console.error("Extraction failed:", error)
    } finally {
      setIsExtracting(false)
    }
  }

  const handleFieldUpdate = (field: string, value: string) => {
    const updates: any = { [field]: value }

    switch (field) {
      case "surgeryType":
        setSurgeryType(value)
        break
      case "hospitalName":
        setHospitalName(value)
        break
      case "doctorName":
        setDoctorName(value)
        break
      case "diagnosis":
        setDiagnosis(value)
        break
      case "medications":
        setMedications(value)
        break
      case "procedureDate":
        setProcedureDate(value)
        break
    }

    onUpdate({
      ...data,
      ...updates
    })
  }

  // surgeryType and procedureDate are optional — not every visit involves surgery
  // or has a clearly stated date in the document.
  const canProceed = files.length > 0 && hospitalName && doctorName && diagnosis

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-3xl mx-auto"
    >
      <div className="bg-white rounded-lg border border-gray-200 p-8">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            Medical Records & Details
          </h2>
          <p className="text-gray-600">
            Upload medical records for AI extraction or fill in details manually
          </p>
        </div>

        <div className="space-y-6">
          {/* File Upload Section */}
          <div>
            <label className="block font-medium text-gray-900 mb-2">
              <FileText className="w-5 h-5 inline mr-2" />
              Upload Medical Records
            </label>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors bg-gray-50">
              <FileText className="w-12 h-12 mx-auto text-gray-400 mb-3" />
              <label className="cursor-pointer">
                <span className="text-blue-600 hover:text-blue-700 font-medium">
                  Choose medical records
                </span>
                <span className="text-gray-700"> or drag and drop</span>
                <input
                  type="file"
                  className="hidden"
                  accept="image/*,.pdf"
                  multiple
                  onChange={handleFileUpload}
                />
              </label>
              <p className="text-xs text-gray-500 mt-2">
                Discharge summary, prescriptions, lab reports, etc.
              </p>
            </div>

            {files.length > 0 && (
              <div className="mt-3 space-y-2">
                {files.map((file, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-2 text-sm text-gray-700 bg-blue-50 p-2 rounded"
                  >
                    <FileText className="w-4 h-4 text-blue-600 flex-shrink-0" />
                    <span className="flex-1 truncate">{file.name}</span>
                    <span className="text-gray-500 flex-shrink-0">
                      {(file.size / 1024).toFixed(1)} KB
                    </span>
                    <button
                      type="button"
                      onClick={() => removeFile(index)}
                      className="flex-shrink-0 text-gray-400 hover:text-red-500 transition-colors"
                      aria-label={`Remove ${file.name}`}
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* AI Extraction Loading */}
          <AnimatePresence>
            {isExtracting && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg border border-blue-200 p-6"
              >
                <div className="flex items-center gap-3">
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{
                      duration: 2,
                      repeat: Infinity,
                      ease: "linear"
                    }}
                  >
                    <Loader className="w-6 h-6 text-blue-600" />
                  </motion.div>
                  <div>
                    <p className="font-medium text-gray-900">
                      AI Extraction in Progress...
                    </p>
                    <p className="text-sm text-gray-600">
                      Analyzing documents with AWS Textract and Comprehend
                      Medical
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* AI Extraction Success */}
          <AnimatePresence>
            {extractedData && !isExtracting && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border border-green-200 p-4"
              >
                <div className="flex items-start gap-3">
                  <Sparkles className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="font-medium text-green-900 mb-1">
                      AI Extraction Completed Successfully!
                    </p>
                    <p className="text-sm text-green-800">
                      Confidence: {(extractedData.confidence * 100).toFixed(0)}%
                      - Review and edit the extracted information below
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Form Fields */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Surgery/Procedure Type *
              </label>
              <input
                type="text"
                value={surgeryType}
                onChange={(e) =>
                  handleFieldUpdate("surgeryType", e.target.value)
                }
                placeholder="e.g., Cardiac Bypass Surgery"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Procedure Date *
              </label>
              <input
                type="date"
                value={procedureDate}
                onChange={(e) =>
                  handleFieldUpdate("procedureDate", e.target.value)
                }
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Hospital Name *
              </label>
              <input
                type="text"
                value={hospitalName}
                onChange={(e) =>
                  handleFieldUpdate("hospitalName", e.target.value)
                }
                placeholder="e.g., City General Hospital"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Doctor Name *
              </label>
              <input
                type="text"
                value={doctorName}
                onChange={(e) =>
                  handleFieldUpdate("doctorName", e.target.value)
                }
                placeholder="e.g., Dr. Sarah Johnson"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Diagnosis *
              </label>
              <input
                type="text"
                value={diagnosis}
                onChange={(e) => handleFieldUpdate("diagnosis", e.target.value)}
                placeholder="e.g., Coronary Artery Disease"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Medications (comma-separated)
              </label>
              <input
                type="text"
                value={medications}
                onChange={(e) =>
                  handleFieldUpdate("medications", e.target.value)
                }
                placeholder="e.g., Aspirin, Metoprolol, Atorvastatin"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
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
            Continue to Review
          </button>
        </div>
      </div>
    </motion.div>
  )
}
