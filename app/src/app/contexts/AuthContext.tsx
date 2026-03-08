/**
 * AuthContext.tsx
 * ===============
 * Thin adapter over react-oidc-context.
 *
 * Exposes a useAuth() hook returning:
 *   user       – { userId, email, name, picture } or null
 *   isLoading  – true while the OIDC session is being resolved
 *   signOut()  – redirects to the Cognito /logout endpoint
 *
 * Also keeps window.__reviewCustomerId in sync with the user sub so that
 * reviewApi.ts can tag document uploads without prop-drilling.
 *
 * AuthProvider is no longer exported from here – it lives in main.tsx
 * (react-oidc-context AuthProvider with cognitoAuthConfig).
 */

import { useEffect } from "react"
import { useAuth as useOidcAuth } from "react-oidc-context"

// ── types ─────────────────────────────────────────────────────────────────────

export interface AppUser {
  /** Cognito sub – stable unique ID used as customerId in document paths */
  userId: string
  email: string
  name: string
  picture?: string
  /** Cognito given_name */
  givenName?: string
  /** Cognito family_name */
  familyName?: string
  /** Cognito phone_number */
  phoneNumber?: string
  /** Cognito address.formatted */
  address?: string
}

export interface AuthAPI {
  user: AppUser | null
  isLoading: boolean
  signOut: () => void
}

// ── hook ──────────────────────────────────────────────────────────────────────

export function useAuth(): AuthAPI {
  const auth = useOidcAuth()

  const user: AppUser | null =
    auth.isAuthenticated && auth.user
      ? {
          userId: auth.user.profile.sub,
          email: (auth.user.profile.email as string) ?? "",
          name:
            (auth.user.profile.name as string) ??
            (auth.user.profile.preferred_username as string) ??
            (auth.user.profile.email as string)?.split("@")[0] ??
            "",
          picture: auth.user.profile.picture as string | undefined,
          givenName: (auth.user.profile.given_name as string) ?? undefined,
          familyName: (auth.user.profile.family_name as string) ?? undefined,
          phoneNumber: (auth.user.profile.phone_number as string) ?? undefined,
          address:
            (auth.user.profile.address as { formatted?: string } | undefined)
              ?.formatted ?? undefined
        }
      : null

  // Keep window.__reviewCustomerId in sync for reviewApi.ts
  useEffect(() => {
    console.log('[AuthContext] useEffect triggered - user:', user?.userId)
    if (user?.userId) {
      ;(window as any).__reviewCustomerId = user.userId
      console.log('[AuthContext] Set window.__reviewCustomerId to:', user.userId)
    } else {
      ;(window as any).__reviewCustomerId = undefined
      console.log('[AuthContext] Cleared window.__reviewCustomerId')
    }
  }, [user?.userId])

  const signOut = () => {
    const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID
    const logoutUri = import.meta.env.VITE_LOGOUT_URI ?? window.location.origin
    const domain = import.meta.env.VITE_COGNITO_DOMAIN

    // Always clear local OIDC state first so the token doesn't linger in
    // sessionStorage. Without this, react-oidc-context still sees the user
    // as authenticated when Cognito redirects back to the app.
    auth.removeUser().then(() => {
      if (domain && clientId) {
        // Cognito requires its own /logout endpoint to invalidate the server-side
        // session (SSO cookie). removeUser() alone only clears local state.
        window.location.href = `${domain}/logout?client_id=${clientId}&logout_uri=${encodeURIComponent(logoutUri)}`
      }
      // If no domain configured (local dev), removeUser() above is sufficient –
      // App.tsx will detect isAuthenticated=false and call signinRedirect().
    })
  }

  return { user, isLoading: auth.isLoading, signOut }
}

// ── utility ───────────────────────────────────────────────────────────────────

/**
 * Returns the current userId (Cognito sub) or "customer_unknown".
 * Safe to call from non-React code (e.g. reviewApi.ts).
 */
export function getCustomerId(): string {
  return (window as any).__reviewCustomerId ?? "customer_unknown"
}
