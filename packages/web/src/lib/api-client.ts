/**
 * Typed API client for Copio backend.
 * All list endpoints return PaginatedResponse format.
 */

export interface Pagination {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: Pagination;
}

export interface ApiError {
  detail: string;
  status: number;
}

class ApiClient {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: HeadersInit = {
      "Content-Type": "application/json",
      ...options.headers,
    };

    const res = await fetch(`/api/v1${endpoint}`, {
      ...options,
      headers,
      credentials: "include",
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Request failed" }));
      throw { detail: error.detail || "Request failed", status: res.status } as ApiError;
    }

    if (res.status === 204) {
      return undefined as T;
    }

    return res.json();
  }

  async list<T>(
    endpoint: string,
    params?: Record<string, string | number | boolean | undefined>
  ): Promise<PaginatedResponse<T>> {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.set(key, String(value));
        }
      });
    }
    const query = searchParams.toString();
    return this.request<PaginatedResponse<T>>(
      `${endpoint}${query ? `?${query}` : ""}`
    );
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint);
  }

  async post<T>(endpoint: string, data: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async patch<T>(endpoint: string, data: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async delete(endpoint: string): Promise<void> {
    return this.request<void>(endpoint, { method: "DELETE" });
  }
}

export const api = new ApiClient();
