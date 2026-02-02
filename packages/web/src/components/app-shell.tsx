"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth.tsx";
import { Sidebar } from "@/components/sidebar";
import { Loader2 } from "lucide-react";

// Routes that don't show the sidebar
const PUBLIC_ROUTES = ["/login", "/register", "/accept-invite", "/forgot-password", "/reset-password"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { isLoading, isAuthenticated } = useAuth();
  
  const isPublicRoute = PUBLIC_ROUTES.some((route) => pathname?.startsWith(route));

  // Show loading spinner while checking auth
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Public routes - no sidebar, centered
  if (isPublicRoute) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-background">
        {children}
      </div>
    );
  }

  // Protected routes - show sidebar if authenticated
  if (isAuthenticated) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    );
  }

  // Not authenticated and not on public route - will redirect via AuthProvider
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  );
}
