/**
 * LoginPage.tsx
 * =============
 * Not rendered directly – auth is handled by the Cognito Hosted UI redirect
 * in App.tsx (via react-oidc-context signinRedirect).
 *
 * This component is kept as a placeholder / loading screen shown momentarily
 * while the OIDC redirect is being initiated.
 */

import { Building2 } from "lucide-react"

export function LoginPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-8 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-2xl mb-4">
          <Building2 className="w-9 h-9 text-blue-600" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Hospital Review
        </h1>
        <p className="text-gray-500 text-sm mb-6">
          Transparent Healthcare Platform
        </p>
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-gray-400 text-sm mt-4">Redirecting to sign-in...</p>
      </div>
    </div>
  )
}
