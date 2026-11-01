/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly ZITADEL_ISSUER: string;
  readonly ZITADEL_CLIENT_ID: string;
  readonly ZITADEL_PROJECT_ID: string;
  readonly VITE_API_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
