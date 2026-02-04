import axios from "axios";

// Use /api/v1 proxy for client-side, direct URL for server-side components
const API_BASE = typeof window !== 'undefined' ? '/api/v1' : (process.env.API_URL || 'http://localhost:8000/api/v1');

// Axios instance for React Query hooks
export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true, // Include cookies in requests
});

// Custom event for session expiry - auth context listens for this
export const SESSION_EXPIRED_EVENT = "session-expired";

export function dispatchSessionExpired() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
  }
}

// Response interceptor for error handling and token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Handle 401 - try to refresh token
    if (error.response?.status === 401 && typeof window !== "undefined" && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // Try to refresh the token
        await axios.post("/api/v1/auth/refresh", {}, { withCredentials: true });
        // Retry the original request
        return api(originalRequest);
      } catch {
        // Refresh failed - show session expired modal instead of redirecting
        if (!window.location.pathname.startsWith("/login")) {
          dispatchSessionExpired();
        }
      }
    }
    return Promise.reject(error);
  }
);

// Legacy fetch wrapper (kept for backward compatibility)
export async function apiFetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
  // Ensure endpoint has trailing slash for collection endpoints (avoids 307 redirects that lose cookies)
  let normalizedEndpoint = endpoint;
  if (!endpoint.includes('?') && !endpoint.match(/\/[a-f0-9-]{36}$/i) && !endpoint.endsWith('/')) {
    normalizedEndpoint = endpoint + '/';
  }
  // Remove leading slash from endpoint if API_BASE ends with one
  const url = normalizedEndpoint.startsWith('/') ? `${API_BASE}${normalizedEndpoint}` : `${API_BASE}/${normalizedEndpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    credentials: "include",
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

// Types matching SQLAlchemy models
export interface Product {
  id: string;
  sku: string;
  name: string;
  description?: string | null;
  category?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Location {
  id: string;
  name: string;
  address?: string | null;
  type: "WAREHOUSE" | "STORE" | "DROPSHIP";
  createdAt: string;
  updatedAt: string;
}

export interface StockItem {
  id: string;
  productId: string;
  locationId: string;
  quantityAvailable: number;
  quantityReserved: number;
  quantityInbound: number;
  costBasis?: number | null;
  createdAt: string;
  updatedAt: string;
  product?: Product;
  location?: Location;
}

export type MovementType = "RECEIVE" | "SHIP" | "ADJUST" | "TRANSFER";

export interface StockMovement {
  id: string;
  stockItemId: string;
  type: MovementType;
  quantity: number;
  notes?: string | null;
  reference?: string | null;
  createdAt: string;
  stockItem?: StockItem;
}
