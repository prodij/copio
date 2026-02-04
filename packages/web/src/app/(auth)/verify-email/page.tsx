"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertCircle, Loader2, CheckCircle, Mail } from "lucide-react";
import Link from "next/link";
import { Logo } from "@/components/logo";

type VerificationStatus = "loading" | "success" | "error" | "no-token";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const justRegistered = searchParams.get("registered") === "true";

  const [status, setStatus] = useState<VerificationStatus>(token ? "loading" : "no-token");
  const [message, setMessage] = useState<string>("");
  const [email, setEmail] = useState<string>("");

  // Resend verification state
  const [resendEmail, setResendEmail] = useState("");
  const [resendLoading, setResendLoading] = useState(false);
  const [resendMessage, setResendMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setStatus("no-token");
      return;
    }

    const verifyEmail = async () => {
      try {
        const res = await fetch(`/api/v1/auth/verify?token=${encodeURIComponent(token)}`, {
          credentials: "include",
        });
        const data = await res.json();

        if (res.ok) {
          setStatus("success");
          setMessage(data.message || "Email verified successfully");
          setEmail(data.email || "");
        } else {
          setStatus("error");
          setMessage(data.detail || "Verification failed");
        }
      } catch {
        setStatus("error");
        setMessage("An error occurred during verification");
      }
    };

    verifyEmail();
  }, [token]);

  const handleResend = async (e: React.FormEvent) => {
    e.preventDefault();
    setResendLoading(true);
    setResendMessage(null);

    try {
      const res = await fetch("/api/v1/auth/resend-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email: resendEmail }),
      });

      const data = await res.json();
      setResendMessage(data.message || "If the email exists and is unverified, a verification link has been sent");
    } catch {
      setResendMessage("Failed to send verification email. Please try again.");
    } finally {
      setResendLoading(false);
    }
  };

  if (status === "loading") {
    return (
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center space-y-4">
          <div className="flex justify-center">
            <Loader2 className="h-12 w-12 animate-spin text-primary" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Verifying your email...</h1>
          <p className="text-muted-foreground">Please wait while we verify your email address.</p>
        </div>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center lg:text-left space-y-2">
          <div className="flex justify-center lg:hidden mb-6">
            <Logo size="lg" />
          </div>
        </div>

        <div className="text-center space-y-4">
          <div className="flex justify-center">
            <div className="h-16 w-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
              <CheckCircle className="h-8 w-8 text-green-600 dark:text-green-400" />
            </div>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Email Verified!</h1>
          <p className="text-muted-foreground">
            {email ? `Your email ${email} has been verified.` : message}
          </p>
          <p className="text-muted-foreground">
            You can now sign in to your account.
          </p>
        </div>

        <Button asChild className="w-full h-11">
          <Link href="/login">Sign in to your account</Link>
        </Button>
      </div>
    );
  }

  // Error or no-token state - show resend form
  return (
    <div className="w-full max-w-sm space-y-8">
      <div className="text-center lg:text-left space-y-2">
        <div className="flex justify-center lg:hidden mb-6">
          <Logo size="lg" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight">
          {justRegistered
            ? "Check Your Email"
            : status === "error"
            ? "Verification Failed"
            : "Verify Your Email"}
        </h1>
        <p className="text-muted-foreground">
          {justRegistered
            ? "We've sent a verification link to your email address. Please check your inbox and click the link to verify your account."
            : status === "error"
            ? message
            : "Enter your email address to receive a new verification link."}
        </p>
      </div>

      {justRegistered && (
        <div className="flex items-center gap-2 text-sm text-green-800 bg-green-100 dark:bg-green-900/30 dark:text-green-300 p-3 rounded-lg">
          <CheckCircle className="h-4 w-4 flex-shrink-0" />
          <span>Account created! Check your email to complete registration.</span>
        </div>
      )}

      {status === "error" && (
        <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 p-3 rounded-lg">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>{message}</span>
        </div>
      )}

      <form onSubmit={handleResend} className="space-y-6">
        {resendMessage && (
          <div className="flex items-center gap-2 text-sm text-green-800 bg-green-100 dark:bg-green-900/30 dark:text-green-300 p-3 rounded-lg">
            <Mail className="h-4 w-4 flex-shrink-0" />
            <span>{resendMessage}</span>
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor="email">Email address</Label>
          <Input
            id="email"
            type="email"
            placeholder="you@example.com"
            value={resendEmail}
            onChange={(e) => setResendEmail(e.target.value)}
            required
            autoComplete="email"
            className="h-11"
          />
        </div>

        <Button type="submit" className="w-full h-11" disabled={resendLoading}>
          {resendLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Resend Verification Email
        </Button>
      </form>

      <p className="text-center text-sm text-muted-foreground">
        Already verified?{" "}
        <Link
          href="/login"
          className="font-medium text-primary hover:underline underline-offset-4"
        >
          Sign in
        </Link>
      </p>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-[400px]">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}
