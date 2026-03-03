import { createRoot } from "react-dom/client"
import { AuthProvider } from "react-oidc-context"
import App from "./app/App.tsx"
import "./styles/index.css"

/**
 * Cognito OIDC configuration.
 * Values come from Vite env vars (.env / .env.production).
 *
 * Required Cognito Hosted-UI settings:
 *   Allowed callback URLs  →  VITE_REDIRECT_URI
 *   Allowed sign-out URLs  →  VITE_LOGOUT_URI
 *   OAuth scopes           →  openid email profile
 */
const cognitoAuthConfig = {
  authority: import.meta.env.VITE_COGNITO_AUTHORITY,
  client_id: import.meta.env.VITE_COGNITO_CLIENT_ID,
  redirect_uri: import.meta.env.VITE_REDIRECT_URI,
  response_type: "code",
  scope: "openid email profile",
  // Automatically redirect back to the page the user was on after sign-in
  onSigninCallback: () => {
    window.history.replaceState({}, document.title, window.location.pathname)
  }
}

createRoot(document.getElementById("root")!).render(
  <AuthProvider {...cognitoAuthConfig}>
    <App />
  </AuthProvider>
)
