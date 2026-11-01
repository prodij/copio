import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";

let tokenProvider: () => Promise<string | null> = async () => null;
export function setTokenProvider(fn: () => Promise<string | null>) {
  tokenProvider = fn;
}

const auth: Middleware = {
  async onRequest({ request }) {
    const token = await tokenProvider();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
};

// The one place that calls fetch (lint blocks it elsewhere). It looks up globalThis.fetch per
// request, so tests can stub it after this module has loaded.
export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_BASE_URL,
  fetch: (request) => globalThis.fetch(request),
});
api.use(auth);
