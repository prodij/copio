import axios from "axios";

// Use /api proxy for client-side, direct URL for server-side components
const API_BASE = typeof window !== 'undefined' ? '/api' : (process.env.API_URL || 'http://localhost:8000/api/v1');

// Axios instance for React Query hooks
export const api = axios.create({
  baseURL: API_BASE,
});

// Request interceptor for auth tokens (future use)
api.interceptors.request.use((config) => {
  // Add auth token if available
  // const token = localStorage.getItem('token');
  // if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle common errors
    if (error.response?.status === 401) {
      // Handle unauthorized
    }
    return Promise.reject(error);
  }
);

// Legacy fetch wrapper (kept for backward compatibility)
export async function apiFetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
  // Remove leading slash from endpoint if API_BASE ends with one
  const url = endpoint.startsWith('/') ? `${API_BASE}${endpoint}` : `${API_BASE}/${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

// Types based on Prisma schema
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
