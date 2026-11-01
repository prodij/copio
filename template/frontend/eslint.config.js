import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "src/api/schema.d.ts"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended, reactHooks.configs.flat.recommended],
    languageOptions: { globals: globals.browser },
  },
  {
    // Raw fetch is only allowed in the typed client (spec section 10).
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/api/client.ts", "src/test/**"],
    rules: {
      "no-restricted-globals": [
        "error",
        { name: "fetch", message: "Use the typed api client in src/api/client.ts" },
      ],
      "no-restricted-properties": [
        "error",
        { object: "globalThis", property: "fetch", message: "Use the typed api client in src/api/client.ts" },
        { object: "window", property: "fetch", message: "Use the typed api client in src/api/client.ts" },
      ],
    },
  },
);
