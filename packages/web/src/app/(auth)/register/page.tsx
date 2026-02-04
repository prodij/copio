"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertCircle, Loader2 } from "lucide-react";
import Link from "next/link";
import { Logo } from "@/components/logo";

export default function RegisterPage() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    tenantName: "",
    email: "",
    password: "",
    confirmPassword: "",
    firstName: "",
    lastName: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const tenantSlug = formData.tenantName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (formData.password !== formData.confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (formData.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    if (!tenantSlug) {
      setError("Please enter a company name");
      return;
    }

    setIsSubmitting(true);

    try {
      const res = await fetch("/api/v1/auth/register-tenant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          tenant_name: formData.tenantName,
          tenant_slug: tenantSlug,
          email: formData.email,
          password: formData.password,
          first_name: formData.firstName || null,
          last_name: formData.lastName || null,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Registration failed");
      }

      const data = await res.json();

      // Check if verification is required
      if (data.verification_required) {
        // Redirect to verify-email page with message
        router.push("/verify-email?registered=true");
      } else {
        // Redirect to login with success message
        router.push("/login?registered=true");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  const updateField = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <div className="w-full max-w-sm space-y-8">
      {/* Header */}
      <div className="text-center lg:text-left space-y-2">
        <div className="flex justify-center lg:hidden mb-6">
          <Logo size="lg" />
        </div>
        <h1 className="text-3xl font-bold tracking-tight">Create your account</h1>
        <p className="text-muted-foreground">
          Start managing your inventory across all channels
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {error && (
          <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 p-3 rounded-lg">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="tenantName">Company Name</Label>
            <Input
              id="tenantName"
              placeholder="Acme Inc"
              value={formData.tenantName}
              onChange={(e) => updateField("tenantName", e.target.value)}
              required
              autoFocus
              className="h-11"
            />
            {tenantSlug && (
              <p className="text-xs text-muted-foreground">
                Your workspace: <span className="font-mono">{tenantSlug}</span>
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="firstName">First Name</Label>
              <Input
                id="firstName"
                placeholder="John"
                value={formData.firstName}
                onChange={(e) => updateField("firstName", e.target.value)}
                className="h-11"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="lastName">Last Name</Label>
              <Input
                id="lastName"
                placeholder="Doe"
                value={formData.lastName}
                onChange={(e) => updateField("lastName", e.target.value)}
                className="h-11"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">Email address</Label>
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={formData.email}
              onChange={(e) => updateField("email", e.target.value)}
              required
              autoComplete="email"
              className="h-11"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              placeholder="••••••••"
              value={formData.password}
              onChange={(e) => updateField("password", e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
              className="h-11"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirmPassword">Confirm Password</Label>
            <Input
              id="confirmPassword"
              type="password"
              placeholder="••••••••"
              value={formData.confirmPassword}
              onChange={(e) => updateField("confirmPassword", e.target.value)}
              required
              className="h-11"
            />
          </div>
        </div>

        <Button type="submit" className="w-full h-11" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Create Account
        </Button>

        <p className="text-xs text-center text-muted-foreground">
          By creating an account, you agree to our{" "}
          <Link href="/terms" className="underline underline-offset-4 hover:text-primary">
            Terms of Service
          </Link>{" "}
          and{" "}
          <Link href="/privacy" className="underline underline-offset-4 hover:text-primary">
            Privacy Policy
          </Link>
        </p>
      </form>

      {/* Divider */}
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background px-2 text-muted-foreground">
            Already have an account?
          </span>
        </div>
      </div>

      {/* Login link */}
      <p className="text-center text-sm text-muted-foreground">
        <Link
          href="/login"
          className="font-medium text-primary hover:underline underline-offset-4"
        >
          Sign in instead
        </Link>
      </p>
    </div>
  );
}
