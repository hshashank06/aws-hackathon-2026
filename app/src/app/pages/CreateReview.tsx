import { useState } from "react"
import { motion } from "motion/react"
import { ProgressSteps } from "../components/ProgressSteps"
import { Step1HospitalSelection } from "../components/review-steps/Step1HospitalSelection"
import { Step2Insurance } from "../components/review-steps/Step2Insurance"
import { Step3MedicalRecords } from "../components/review-steps/Step3MedicalRecords"
import { Step4ReviewSubmission } from "../components/review-steps/Step4ReviewSubmission"

const STEPS = [
  {
    number: 1,
    title: "Hospital & Documents",
    description: "Select hospital and verify"
  },
  {
    number: 2,
    title: "Insurance",
    description: "Optional coverage details"
  },
  {
    number: 3,
    title: "Medical Records",
    description: "AI extracts details"
  },
  {
    number: 4,
    title: "Review",
    description: "Rate and submit"
  }
]

export function CreateReview() {
  const [currentStep, setCurrentStep] = useState(1)
  const [formData, setFormData] = useState({
    // Step 1
    hospitalId: "",
    verificationFiles: [] as File[],
    documentsVerified: false,
    documentIds: [] as string[], // s3 keys from Step 1 bill validation
    payment: null as any, // payment object from bill processing

    // Step 2
    hasInsurance: false,
    insuranceCompanyId: "",
    claimFiles: [] as File[],
    claimVerified: true,
    claimData: null as any, // claim object from claim processing
    claimDocumentIds: [] as string[], // s3 keys from Step 2 claim validation

    // Step 3
    medicalRecordFiles: [] as File[],
    medicalRecordDocumentIds: [] as string[],
    extractedData: null,
    surgeryType: "",
    hospitalName: "",
    doctorName: "",
    diagnosis: "",
    medications: "",
    procedureDate: "",

    // Step 4
    doctorId: "",
    hospitalRating: 0,
    hospitalReview: "",
    doctorRating: 0,
    doctorReview: "",
    totalCost: 0,
    insuranceCovered: 0
  })

  const updateFormData = (stepData: any) => {
    setFormData((prev) => ({ ...prev, ...stepData }))
  }

  const handleNext = () => {
    if (currentStep < STEPS.length) {
      setCurrentStep(currentStep + 1)
      window.scrollTo({ top: 0, behavior: "smooth" })
    }
  }

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1)
      window.scrollTo({ top: 0, behavior: "smooth" })
    }
  }

  return (
    <div className="min-h-full bg-gray-50 py-8">
      <div className="max-w-5xl mx-auto px-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Create a Verified Review
          </h1>
          <p className="text-gray-600">
            Help others make informed healthcare decisions with your authentic
            experience
          </p>
        </motion.div>

        {/* Progress Steps */}
        <ProgressSteps steps={STEPS} currentStep={currentStep} />

        {/* Step Content */}
        <div className="mt-8">
          {currentStep === 1 && (
            <Step1HospitalSelection
              data={{
                hospitalId: formData.hospitalId,
                verificationFiles: formData.verificationFiles,
                documentsVerified: formData.documentsVerified
              }}
              onUpdate={updateFormData}
              onNext={handleNext}
            />
          )}

          {currentStep === 2 && (
            <Step2Insurance
              data={{
                hasInsurance: formData.hasInsurance,
                insuranceCompanyId: formData.insuranceCompanyId,
                claimFiles: formData.claimFiles,
                claimVerified: formData.claimVerified
              }}
              onUpdate={updateFormData}
              onNext={handleNext}
              onBack={handleBack}
            />
          )}

          {currentStep === 3 && (
            <Step3MedicalRecords
              data={{
                medicalRecordFiles: formData.medicalRecordFiles,
                medicalRecordDocumentIds: formData.medicalRecordDocumentIds,
                extractedData: formData.extractedData,
                surgeryType: formData.surgeryType,
                hospitalName: formData.hospitalName,
                doctorName: formData.doctorName,
                diagnosis: formData.diagnosis,
                medications: formData.medications,
                procedureDate: formData.procedureDate
              }}
              onUpdate={updateFormData}
              onNext={handleNext}
              onBack={handleBack}
            />
          )}

          {currentStep === 4 && (
            <Step4ReviewSubmission
              data={{
                hospitalRating: formData.hospitalRating,
                hospitalReview: formData.hospitalReview,
                doctorRating: formData.doctorRating,
                doctorReview: formData.doctorReview,
                totalCost: formData.totalCost,
                insuranceCovered: formData.insuranceCovered,
                doctorName: formData.doctorName,
                surgeryType: formData.surgeryType,
                doctorId: formData.doctorId,
                serviceRating: (formData as any).serviceRating ?? 0,
                maintenanceRating: (formData as any).maintenanceRating ?? 0,
                foodRating: (formData as any).foodRating ?? 0,
                cleanlinessRating: (formData as any).cleanlinessRating ?? 0,
                staffRating: (formData as any).staffRating ?? 0,
                bedsideMannerRating: (formData as any).bedsideMannerRating ?? 0,
                expertiseRating: (formData as any).expertiseRating ?? 0,
                communicationRating: (formData as any).communicationRating ?? 0,
                waitTimeRating: (formData as any).waitTimeRating ?? 0,
                thoroughnessRating: (formData as any).thoroughnessRating ?? 0,
                followUpRating: (formData as any).followUpRating ?? 0
              }}
              onUpdate={updateFormData}
              onBack={handleBack}
              allData={formData}
            />
          )}
        </div>
      </div>
    </div>
  )
}
