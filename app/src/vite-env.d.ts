/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Cognito OIDC authority – https://cognito-idp.<region>.amazonaws.com/<poolId> */
  readonly VITE_COGNITO_AUTHORITY: string
  /** Cognito app client ID */
  readonly VITE_COGNITO_CLIENT_ID: string
  /** Cognito hosted-UI domain – https://<domain>.auth.<region>.amazoncognito.com */
  readonly VITE_COGNITO_DOMAIN: string
  /** OAuth callback URL – http://localhost:5173 in dev, CloudFront URL in prod */
  readonly VITE_REDIRECT_URI: string
  /** Post-logout redirect URL */
  readonly VITE_LOGOUT_URI: string
  /** Backend API base URL */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
