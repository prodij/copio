"use client";

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";

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
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

// Token storage
const TOKEN_KEY = "copio_token";

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// Auth API calls
async function loginApi(email: string, password: string): Promise<{ access_token: string; token_type: string }> {
  const res = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: email, password }),
  });
  
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Login failed" }));
    // Map common error codes to user-friendly messages
    const detail = error.detail || "Login failed";
    if (detail === "LOGIN_BAD_CREDENTIALS" || detail.includes("credentials")) {
      throw new Error("Invalid email or password");
    }
    if (detail === "LOGIN_USER_NOT_VERIFIED") {
      throw new Error("Please verify your email before logging in");
    }
    throw new Error(detail);
  }
  
  return res.json();
}

async function getMeApi(token: string): Promise<User> {
  const res = await fetch("/api/v1/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
  
  if (!res.ok) {
    throw new Error("Failed to get user");
  }
  
  const data = await res.json();
  return {
    id: data.id,
    email: data.email,
    firstName: data.first_name,
    lastName: data.last_name,
    role: data.role,
    tenantId: data.tenant_id,
    isActive: data.is_active,
    isVerified: data.is_verified,
  };
}

async function logoutApi(token: string): Promise<void> {
  await fetch("/api/v1/auth/logout", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

// Public routes that don't require auth
const PUBLIC_ROUTES = ["/login", "/register", "/accept-invite", "/forgot-password", "/reset-password"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const isPublicRoute = PUBLIC_ROUTES.some((route) => pathname?.startsWith(route));

  // Initialize auth state from stored token
  useEffect(() => {
    const initAuth = async () => {
      const storedToken = getStoredToken();
      if (storedToken) {
        try {
          const userData = await getMeApi(storedToken);
          setUser(userData);
          setToken(storedToken);
        } catch {
          // Token invalid, clear it
          clearStoredToken();
        }
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  // Redirect logic
  useEffect(() => {
    if (isLoading) return;

    if (!user && !isPublicRoute) {
      router.push("/login");
    } else if (user && isPublicRoute && pathname !== "/accept-invite") {
      router.push("/");
    }
  }, [user, isLoading, isPublicRoute, pathname, router]);

  const login = useCallback(async (email: string, password: string) => {
    const result = await loginApi(email, password);
    const newToken = result.access_token;
    
    setStoredToken(newToken);
    setToken(newToken);
    
    const userData = await getMeApi(newToken);
    setUser(userData);
    
    router.push("/");
  }, [router]);

  const logout = useCallback(async () => {
    if (token) {
      try {
        await logoutApi(token);
      } catch {
        // Ignore logout API errors
      }
    }
    
    clearStoredToken();
    setToken(null);
    setUser(null);
    router.push("/login");
  }, [token, router]);

  const refreshUser = useCallback(async () => {
    if (token) {
      const userData = await getMeApi(token);
      setUser(userData);
    }
  }, [token]);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
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

// Hook for adding auth header to fetch requests
export function useAuthFetch() {
  const { token } = useAuth();
  
  return useCallback(
    async (url: string, options?: RequestInit) => {
      const headers: HeadersInit = {
        ...options?.headers,
      };
      
      if (token) {
        (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
      }
      
      return fetch(url, { ...options, headers });
    },
    [token]
  );
}
