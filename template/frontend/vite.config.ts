import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Public (browser-visible) config only: VITE_* and ZITADEL_* names, shared with Compose.
  // Every variable with these prefixes in the environment lands in the bundle, so never run Vite
  // with a secret named ZITADEL_* (the Makefile unexports ZITADEL_MASTERKEY; the frontend
  // container gets only ZITADEL_ISSUER, ZITADEL_CLIENT_ID and ZITADEL_PROJECT_ID).
  envPrefix: ["VITE_", "ZITADEL_"],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  test: {
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    env: { VITE_API_BASE_URL: "http://api.test" },
  },
});
