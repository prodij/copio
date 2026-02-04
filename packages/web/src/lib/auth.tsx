"use client";

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { SessionExpiredModal } from "@/components/session-expired-modal";

// Types
export interface User {
  id: string;
  email: string;
  firstName: string | null;
  lastName: string | null;
  role: string;
  tenantId: string;
  isActive: boolean;
  isVerified: boolean;
  isSuperuser: boolean;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  onboardingComplete: boolean;
}

interface AuthContextType {
  user: User | null;
  tenant: Tenant | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  sessionExpired: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  showSessionExpired: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

// Public routes that don't require auth
const PUBLIC_ROUTES = ["/login", "/register", "/accept-invite", "/forgot-password", "/reset-password", "/verify-email", "/onboarding"];

// Helper function to make fetch requests with automatic token refresh on 401
async function fetchWithRefresh(url: string, options?: RequestInit): Promise<Response> {
  const res = await fetch(url, { ...options, credentials: "include" });

  if (res.status === 401) {
    // Try to refresh the token
    const refreshRes = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      credentials: "include",
    });

    if (refreshRes.ok) {
      // Retry the original request
      return fetch(url, { ...options, credentials: "include" });
    }
    // Refresh failed, throw error to trigger logout
    throw new Error("Session expired");
  }

  return res;
}

// Auth API calls
interface LoginApiResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    first_name: string | null;
    last_name: string | null;
  };
  tenant: {
    id: string;
    name: string;
    slug: string;
    onboarding_complete: boolean;
  };
}

async function loginApi(email: string, password: string): Promise<LoginApiResponse> {
  const res = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Login failed" }));
    // Map common error codes to user-friendly messages
    // detail might be a string or an object (Pydantic validation errors)
    const detail = typeof error.detail === "string" ? error.detail : "Login failed";
    if (detail === "LOGIN_BAD_CREDENTIALS" || detail.includes("credentials") || detail.includes("Invalid email")) {
      throw new Error("Invalid email or password");
    }
    // 403 with verification message
    if (res.status === 403 || detail.toLowerCase().includes("verify your email")) {
      throw new Error("Please verify your email before logging in");
    }
    if (detail === "LOGIN_USER_NOT_VERIFIED") {
      throw new Error("Please verify your email before logging in");
    }
    throw new Error(detail);
  }

  return res.json();
}

interface MeApiResponse {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  role: string;
  tenant_id: string;
  is_active: boolean;
  is_verified: boolean;
  is_superuser: boolean;
}

async function getMeApi(): Promise<User> {
  const res = await fetchWithRefresh("/api/v1/auth/me", {
    credentials: "include",
  });

  if (!res.ok) {
    throw new Error("Failed to get user");
  }

  const data: MeApiResponse = await res.json();
  return {
    id: data.id,
    email: data.email,
    firstName: data.first_name,
    lastName: data.last_name,
    role: data.role,
    tenantId: data.tenant_id,
    isActive: data.is_active,
    isVerified: data.is_verified,
    isSuperuser: data.is_superuser,
  };
}

async function logoutApi(): Promise<void> {
  await fetch("/api/v1/auth/logout", {
    method: "POST",
    credentials: "include",
  });
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  const isPublicRoute = PUBLIC_ROUTES.some((route) => pathname?.startsWith(route));

  // Clear auth state helper
  const clearAuthState = useCallback(() => {
    setUser(null);
    setTenant(null);
  }, []);

  // Show session expired modal
  const showSessionExpired = useCallback(() => {
    setSessionExpired(true);
  }, []);

  // Handle login from session expired modal
  const handleSessionExpiredLogin = useCallback(() => {
    setSessionExpired(false);
    clearAuthState();
    router.push("/login");
  }, [clearAuthState, router]);

  // Listen for session expired events from axios interceptor
  useEffect(() => {
    const handleSessionExpiredEvent = () => {
      showSessionExpired();
    };

    window.addEventListener("session-expired", handleSessionExpiredEvent);
    return () => {
      window.removeEventListener("session-expired", handleSessionExpiredEvent);
    };
  }, [showSessionExpired]);

  // Initialize auth state by checking if we have a valid session
  useEffect(() => {
    const initAuth = async () => {
      try {
        // Try to get current user - if cookies are valid, this will work
        const userData = await getMeApi();
        setUser(userData);
        // Note: We don't have tenant info from /me endpoint,
        // tenant will be set on login or we could add a separate endpoint
      } catch {
        // No valid session, clear state
        clearAuthState();
      }
      setIsLoading(false);
    };

    initAuth();
  }, [clearAuthState]);

  // Redirect logic
  useEffect(() => {
    if (isLoading) return;

    if (!user && !isPublicRoute) {
      router.push("/login");
    } else if (user && isPublicRoute && pathname !== "/accept-invite") {
      // If onboarding is not complete, redirect to onboarding
      if (tenant && !tenant.onboardingComplete && pathname !== "/onboarding") {
        router.push("/onboarding");
      } else if (pathname !== "/onboarding") {
        router.push("/");
      }
    }
  }, [user, tenant, isLoading, isPublicRoute, pathname, router]);

  const login = useCallback(async (email: string, password: string) => {
    const result = await loginApi(email, password);

    // Set tenant from login response (this is the only place we get tenant info)
    setTenant({
      id: result.tenant.id,
      name: result.tenant.name,
      slug: result.tenant.slug,
      onboardingComplete: result.tenant.onboarding_complete,
    });

    // Fetch complete user data from /me endpoint to get role, etc.
    const userData = await getMeApi();
    setUser(userData);

    // Check if onboarding is complete
    if (!result.tenant.onboarding_complete) {
      router.push("/onboarding");
    } else {
      router.push("/");
    }
  }, [router]);

  const logout = useCallback(async () => {
    try {
      await logoutApi();
    } catch {
      // Ignore logout API errors
    }

    clearAuthState();
    router.push("/login");
  }, [clearAuthState, router]);

  const refreshUser = useCallback(async () => {
    try {
      const userData = await getMeApi();
      setUser(userData);
    } catch {
      // Session expired, show modal instead of silently redirecting
      showSessionExpired();
    }
  }, [showSessionExpired]);

  return (
    <AuthContext.Provider
      value={{
        user,
        tenant,
        isLoading,
        isAuthenticated: !!user,
        sessionExpired,
        login,
        logout,
        refreshUser,
        showSessionExpired,
      }}
    >
      {children}
      <SessionExpiredModal
        open={sessionExpired}
        onLogin={handleSessionExpiredLogin}
      />
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

// Hook for making authenticated fetch requests with automatic token refresh
export function useAuthFetch() {
  const { showSessionExpired } = useAuth();

  return useCallback(
    async (url: string, options?: RequestInit) => {
      try {
        return await fetchWithRefresh(url, options);
      } catch (error) {
        if (error instanceof Error && error.message === "Session expired") {
          showSessionExpired();
        }
        throw error;
      }
    },
    [showSessionExpired]
  );
}
