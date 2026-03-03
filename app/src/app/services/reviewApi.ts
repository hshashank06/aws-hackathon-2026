/**
 * reviewApi.ts
 * ============
 * Real API client for the review submission workflow.
 *
 * Flow per document type:
 *   1. POST /reviews/presign          → get pre-signed S3 PUT URL + s3Key
 *   2. PUT  <presignedUrl>            → upload file directly to S3 from browser
 *   3. POST /reviews/process-document → trigger Step Functions Sync Express Workflow
 *                                        (Rekognition → Textract → Comprehend/Comprehend Medical)
 *                                        returns extracted fields
 *   4. POST /reviews                  → submit assembled review (Lambda → Bedrock → DynamoDB)
 *
 * S3 prefixes:
 *   hospitalBill   → documents/hospitalBills/
 *   insuranceClaim → documents/insuranceClaims/
 *   medicalRecord  → documents/medicalRecords/
 */

// ---------------------------------------------------------------------------
// Config  –  set VITE_API_BASE_URL in your .env file
// ---------------------------------------------------------------------------
const API_BASE_URL: string =
  (import.meta as any).env?.VITE_API_BASE_URL?.replace(/\/$/, "") ?? ""

// ---------------------------------------------------------------------------
// Exported interfaces (unchanged so existing callers keep working)
// ---------------------------------------------------------------------------

export interface DocumentValidationResult {
  success: boolean
  verified: boolean
  s3Url?: string
  documentId?: string
  message: string
  confidence?: number
  /** Raw payment object returned by the Step Functions bill-processing workflow */
  payment?: any
  /** Raw claim object returned by the Step Functions claim-processing workflow */
  claimData?: any
}

export interface ExtractedMedicalData {
  hospitalName: string
  doctorName: string
  surgeryType: string
  procedureDate: string
  diagnosis: string
  medications: string[]
  confidence: number
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Derive a MIME type from the file's extension (more reliable than file.type). */
function mimeFromExtension(file: File): string {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? ""
  const map: Record<string, string> = {
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    png: "image/png",
    gif: "image/gif",
    webp: "image/webp",
    bmp: "image/bmp",
    tiff: "image/tiff",
    pdf: "application/pdf"
  }
  return map[ext] ?? file.type ?? "application/octet-stream"
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error((err as any).error ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

async function apiDelete<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error((err as any).error ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

/**
 * Delete a previously-uploaded document from S3.
 * documentId == s3Key returned by the presign endpoint.
 * Silently succeeds if the object no longer exists.
 */
export async function deleteDocument(documentId: string): Promise<void> {
  try {
    await apiDelete<any>("/reviews/documents", { documentId })
    console.log(`[Document API] Deleted document from S3: ${documentId}`)
  } catch (err: any) {
    // Log but don't rethrow – a failed S3 delete shouldn't block the UI
    console.warn(
      `[Document API] Failed to delete document '${documentId}' from S3: ${err.message}`
    )
  }
}

/**
 * Upload a file directly to S3 via a pre-signed PUT URL.
 * Returns the s3Key (= documentId) for use in subsequent API calls.
 */
async function uploadToS3(
  file: File,
  customerId: string,
  documentType: "hospitalBill" | "insuranceClaim" | "medicalRecord"
): Promise<{ uploadUrl: string; s3Key: string; documentId: string }> {
  const presign = await apiPost<{
    uploadUrl: string
    s3Key: string
    documentId: string
    expiresIn: number
  }>("/reviews/presign", {
    customerId,
    filename: file.name,
    documentType
  })
  const uploadRes = await fetch(presign.uploadUrl, {
    method: "PUT",
    headers: { "Content-Type": mimeFromExtension(file) },
    body: file
  })

  if (!uploadRes.ok) {
    throw new Error(`S3 upload failed: ${uploadRes.statusText}`)
  }

  return presign
}

/**
 * Trigger the Step Functions document-processing workflow for a single file
 * that has already been uploaded to S3.
 */
async function processDocument(
  s3Key: string,
  documentId: string,
  documentType: "hospitalBill" | "insuranceClaim" | "medicalRecord"
): Promise<any> {
  return apiPost<any>("/reviews/process-document", {
    documentId,
    s3Key,
    documentType
  })
}

// ---------------------------------------------------------------------------
// Exported API functions (same signatures as the former mocks)
// ---------------------------------------------------------------------------

/**
 * Validate a hospital bill document:
 *   upload → S3  →  Rekognition (valid?) → Textract → Comprehend → payment{}
 *
 * Expects window.__reviewCustomerId to be set before calling.
 */
export async function validateDocument(
  file: File
): Promise<DocumentValidationResult> {
  console.log(`[Document Validation API] Uploading & validating: ${file.name}`)

  const customerId: string =
    (window as any).__reviewCustomerId ?? "customer_unknown"

  try {
    const { s3Key, documentId } = await uploadToS3(
      file,
      customerId,
      "hospitalBill"
    )
    const result = await processDocument(s3Key, documentId, "hospitalBill")

    console.log(`[Document Validation API] Result for ${file.name}:`, result)

    // `valid` may be absent – infer success from the presence of extracted data
    const verified =
      result.valid ?? (result.payment != null || result.documentId != null)
    return {
      success: verified,
      verified: verified,
      s3Url: result.s3Url,
      documentId: result.documentId,
      message: verified
        ? "Hospital bill verified successfully"
        : `Verification failed: ${result.reason ?? "unknown reason"}`,
      confidence: result.confidence,
      payment: result.payment
    }
  } catch (err: any) {
    console.error(`[Document Validation API] Error: ${err.message}`)
    return {
      success: false,
      verified: false,
      message: err.message ?? "Document validation failed"
    }
  }
}

/**
 * Validate an insurance claim document:
 *   upload → S3  →  Rekognition → Textract → Comprehend → claim{}
 */
export async function validateInsuranceClaim(
  claimFile: File
): Promise<DocumentValidationResult> {
  console.log(
    `[Insurance Validation API] Uploading & validating: ${claimFile.name}`
  )

  const customerId: string =
    (window as any).__reviewCustomerId ?? "customer_unknown"

  try {
    const { s3Key, documentId } = await uploadToS3(
      claimFile,
      customerId,
      "insuranceClaim"
    )
    const result = await processDocument(s3Key, documentId, "insuranceClaim")

    console.log(
      `[Insurance Validation API] Result for ${claimFile.name}:`,
      result
    )

    // `valid` may be absent – infer success from the presence of extracted data
    const verified =
      result.valid ?? (result.claim != null || result.documentId != null)
    return {
      success: verified,
      verified: verified,
      s3Url: result.s3Url,
      documentId: result.documentId,
      message: verified
        ? "Insurance claim document verified"
        : `Verification failed: ${result.reason ?? "unknown reason"}`,
      confidence: result.confidence,
      claimData: result.claim
    }
  } catch (err: any) {
    console.error(`[Insurance Validation API] Error: ${err.message}`)
    return {
      success: false,
      verified: false,
      message: err.message ?? "Insurance claim validation failed"
    }
  }
}

/**
 * Extract medical data from one or more medical record files:
 *   per file: upload → S3 → Rekognition → Textract → Comprehend Medical → extractedData{}
 *   Results from multiple files are merged (highest confidence wins per field).
 */
export async function extractMedicalData(
  files: File[]
): Promise<ExtractedMedicalData> {
  console.log(`[Medical Extraction API] Processing ${files.length} file(s)`)

  const customerId: string =
    (window as any).__reviewCustomerId ?? "customer_unknown"

  const results: any[] = []

  for (const file of files) {
    try {
      const { s3Key, documentId } = await uploadToS3(
        file,
        customerId,
        "medicalRecord"
      )
      const result = await processDocument(s3Key, documentId, "medicalRecord")
      if (result?.extractedData) {
        results.push(result)
      }
    } catch (err: any) {
      console.warn(
        `[Medical Extraction API] Skipping ${file.name}: ${err.message}`
      )
    }
  }

  if (results.length === 0) {
    throw new Error("Medical data extraction failed for all uploaded files.")
  }

  // Merge: pick the result with the highest overall confidence as the base,
  // then fill in any missing fields from lower-confidence results.
  results.sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0))
  const best = results[0].extractedData as ExtractedMedicalData

  for (const r of results.slice(1)) {
    const ed = r.extractedData as Partial<ExtractedMedicalData>
    if (!best.hospitalName && ed.hospitalName)
      best.hospitalName = ed.hospitalName
    if (!best.doctorName && ed.doctorName) best.doctorName = ed.doctorName
    if (!best.surgeryType && ed.surgeryType) best.surgeryType = ed.surgeryType
    if (!best.procedureDate && ed.procedureDate)
      best.procedureDate = ed.procedureDate
    if (!best.diagnosis && ed.diagnosis) best.diagnosis = ed.diagnosis
    if (ed.medications?.length && !best.medications?.length) {
      best.medications = ed.medications
    }
  }

  console.log(`[Medical Extraction API] Merged extractedData:`, best)
  return best
}

/**
 * Submit the fully assembled review to the backend.
 * The Lambda will call Bedrock to generate payment.description, then write to DynamoDB.
 */
export async function submitReview(
  reviewData: any
): Promise<{ success: boolean; reviewId: string }> {
  console.log(`[Review Submission API] Submitting review`)

  try {
    const result = await apiPost<any>("/reviews", reviewData)

    console.log(`[Review Submission API] Created reviewId: ${result.reviewId}`)
    return { success: true, reviewId: result.reviewId }
  } catch (err: any) {
    console.error(`[Review Submission API] Error: ${err.message}`)
    throw err
  }
}
