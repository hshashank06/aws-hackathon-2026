import { useEffect } from "react"
import { useAuth } from "react-oidc-context"
import { BrowserRouter, Routes, Route } from "react-router-dom"
import { Layout } from "./components/Layout"
import { Home } from "./pages/Home"
import { CreateReview } from "./pages/CreateReview"
import { PastReviews } from "./pages/PastReviews"
import { MyDocuments } from "./pages/MyDocuments"
import { MyDetails } from "./pages/MyDetails"
import { HospitalDetail } from "./pages/HospitalDetail"

export default function App() {
  const auth = useAuth()

  useEffect(() => {
    if (!auth.isLoading && !auth.isAuthenticated && !auth.error) {
      auth.signinRedirect()
    }
  }, [auth.isLoading, auth.isAuthenticated, auth.error])

  if (auth.isLoading || (!auth.isAuthenticated && !auth.error)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-500 text-sm">Signing in...</p>
        </div>
      </div>
    )
  }

  if (auth.error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-md">
          <p className="text-red-600 font-medium mb-2">Authentication error</p>
          <p className="text-gray-500 text-sm mb-4">{auth.error.message}</p>
          <button
            onClick={() => auth.signinRedirect()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
          >
            Try again
          </button>
        </div>
      </div>
    )
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="create-review" element={<CreateReview />} />
          <Route path="past-reviews" element={<PastReviews />} />
          <Route path="my-reviews" element={<PastReviews />} />
          <Route path="my-documents" element={<MyDocuments />} />
          <Route path="my-details" element={<MyDetails />} />
          <Route path="hospital/:id" element={<HospitalDetail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
