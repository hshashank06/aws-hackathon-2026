import { useState, useEffect } from "react"
import { Upload, CheckCircle, XCircle, Loader, FileText } from "lucide-react"
import { motion, AnimatePresence } from "motion/react"
import {
  validateDocument,
  deleteDocument,
  DocumentValidationResult
} from "../services/reviewApi"

interface FileUploadProps {
  label: string
  description?: string
  accept?: string
  multiple?: boolean
  customerId: string  // ← Add customerId prop
  /** Override the validation function (e.g. validateInsuranceClaim). Defaults to validateDocument (hospitalBill). */
  validateFn?: (file: File, customerId: string) => Promise<DocumentValidationResult>
  onVerificationComplete: (
    files: File[],
    allVerified: boolean,
    results: DocumentValidationResult[]
  ) => void
}

interface FileStatus {
  file: File
  status: "pending" | "validating" | "verified" | "failed"
  message?: string
  confidence?: number
  result?: DocumentValidationResult
}

export function FileUploadWithVerification({
  label,
  description,
  accept = "image/*,.pdf",
  multiple = true,
  customerId,
  validateFn = validateDocument,
  onVerificationComplete
}: FileUploadProps) {
  const [files, setFiles] = useState<FileStatus[]>([])
  const [isDragging, setIsDragging] = useState(false)

  // Use effect to notify parent when files change
  useEffect(() => {
    if (files.length > 0) {
      const allFiles = files.map((f) => f.file)
      const allVerified = files.every((f) => f.status === "verified")
      const results = files
        .map((f) => f.result)
        .filter(Boolean) as DocumentValidationResult[]
      onVerificationComplete(allFiles, allVerified, results)
    } else {
      onVerificationComplete([], false, [])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [files])

  const handleFiles = async (fileList: FileList) => {
    const newFiles: FileStatus[] = Array.from(fileList).map((file) => ({
      file,
      status: "pending" as const
    }))

    setFiles((prev) => [...prev, ...newFiles])

    // Validate each file
    for (let i = 0; i < newFiles.length; i++) {
      const fileStatus = newFiles[i]
      const index = files.length + i

      // Update status to validating
      setFiles((prev) => {
        const updated = [...prev]
        updated[index] = { ...updated[index], status: "validating" }
        return updated
      })

      // Call validation API
      const result = await validateFn(fileStatus.file, customerId)

      // Update status with result
      setFiles((prev) => {
        const updated = [...prev]
        updated[index] = {
          ...updated[index],
          status: result.verified ? "verified" : "failed",
          message: result.message,
          confidence: result.confidence,
          result
        }
        return updated
      })
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files) {
      handleFiles(e.dataTransfer.files)
    }
  }

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      handleFiles(e.target.files)
    }
  }

  const removeFile = (index: number) => {
    const fileStatus = files[index]
    // If the file was already uploaded to S3, delete it there too
    if (fileStatus?.result?.documentId) {
      deleteDocument(fileStatus.result.documentId)
    }
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-3">
      <label className="block font-medium text-gray-900">{label}</label>
      {description && (
        <p className="text-sm text-gray-600 -mt-2">{description}</p>
      )}

      {/* Upload Area */}
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          isDragging
            ? "border-blue-500 bg-blue-50"
            : "border-gray-300 hover:border-gray-400 bg-gray-50"
        }`}
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <Upload className="w-12 h-12 mx-auto text-gray-400 mb-3" />
        <p className="text-sm text-gray-700 mb-2">
          Drag and drop your files here, or{" "}
          <label className="text-blue-600 hover:text-blue-700 cursor-pointer font-medium">
            browse
            <input
              type="file"
              className="hidden"
              accept={accept}
              multiple={multiple}
              onChange={handleFileInput}
            />
          </label>
        </p>
        <p className="text-xs text-gray-500">Supports PDF, JPG, PNG files</p>
      </div>

      {/* File List */}
      <AnimatePresence>
        {files.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="space-y-2"
          >
            {files.map((fileStatus, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className={`flex items-center gap-3 p-3 rounded-lg border ${
                  fileStatus.status === "verified"
                    ? "bg-green-50 border-green-200"
                    : fileStatus.status === "failed"
                      ? "bg-red-50 border-red-200"
                      : "bg-white border-gray-200"
                }`}
              >
                <FileText className="w-5 h-5 text-gray-600 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {fileStatus.file.name}
                  </p>
                  <p className="text-xs text-gray-500">
                    {(fileStatus.file.size / 1024).toFixed(1)} KB
                  </p>
                  {fileStatus.message && (
                    <p
                      className={`text-xs mt-1 ${
                        fileStatus.status === "verified"
                          ? "text-green-700"
                          : "text-red-700"
                      }`}
                    >
                      {fileStatus.message}
                      {fileStatus.confidence && (
                        <span className="ml-1">
                          (Confidence:{" "}
                          {(fileStatus.confidence * 100).toFixed(0)}%)
                        </span>
                      )}
                    </p>
                  )}
                </div>

                {/* Status Icon */}
                <div className="flex-shrink-0">
                  {fileStatus.status === "validating" && (
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{
                        duration: 1,
                        repeat: Infinity,
                        ease: "linear"
                      }}
                    >
                      <Loader className="w-5 h-5 text-blue-600" />
                    </motion.div>
                  )}
                  {fileStatus.status === "verified" && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: "spring", stiffness: 200 }}
                    >
                      <CheckCircle className="w-5 h-5 text-green-600" />
                    </motion.div>
                  )}
                  {fileStatus.status === "failed" && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: "spring", stiffness: 200 }}
                    >
                      <XCircle className="w-5 h-5 text-red-600" />
                    </motion.div>
                  )}
                </div>

                {/* Remove Button */}
                <button
                  onClick={() => removeFile(index)}
                  className="text-gray-400 hover:text-gray-600 text-sm flex-shrink-0"
                >
                  Remove
                </button>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
