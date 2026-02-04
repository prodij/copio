"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { Shield, Mail } from "lucide-react";
import { toast } from "sonner";

interface SystemSetting {
  id: string;
  key: string;
  value: Record<string, unknown>;
  description: string | null;
  created_at: string;
  updated_at: string;
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-72" />
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-64" />
            </div>
            <Skeleton className="h-6 w-11 rounded-full" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function AdminSettingsPage() {
  const { isAuthenticated } = useAuth();
  const [settings, setSettings] = useState<SystemSetting[]>([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated) return;

    fetch("/api/v1/admin/settings", {
      credentials: "include",
    })
      .then((r) => {
        if (r.ok) return r.json();
        throw new Error("Failed to load settings");
      })
      .then(setSettings)
      .catch((err) => {
        toast.error(err.message);
      })
      .finally(() => setLoading(false));
  }, [isAuthenticated]);

  const updateSetting = async (key: string, value: Record<string, unknown>) => {
    setUpdating(key);
    try {
      const res = await fetch(`/api/v1/admin/settings/${key}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({ value }),
      });

      if (res.ok) {
        const updated = await res.json();
        setSettings((prev) =>
          prev.map((s) => (s.key === key ? updated : s))
        );
        toast.success("Setting updated");
      } else {
        const err = await res.json();
        toast.error(err.detail || "Failed to update setting");
      }
    } catch {
      toast.error("Failed to update setting");
    } finally {
      setUpdating(null);
    }
  };

  const getEmailVerificationSetting = () => {
    return settings.find((s) => s.key === "require_email_verification");
  };

  const toggleEmailVerification = async () => {
    const setting = getEmailVerificationSetting();
    if (!setting) return;

    const currentValue = (setting.value as { enabled?: boolean })?.enabled ?? true;
    await updateSetting(setting.key, { enabled: !currentValue });
  };

  if (loading) return <LoadingSkeleton />;

  const emailVerificationSetting = getEmailVerificationSetting();
  const emailVerificationEnabled =
    (emailVerificationSetting?.value as { enabled?: boolean })?.enabled ?? true;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <Shield className="h-8 w-8" />
          System Settings
        </h1>
        <p className="text-muted-foreground mt-1">
          Global configuration settings. Only superusers can access this area.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5" />
            Authentication Settings
          </CardTitle>
          <CardDescription>
            Configure how users authenticate with the system
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {emailVerificationSetting ? (
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="email-verification" className="text-base">
                  Require Email Verification
                </Label>
                <p className="text-sm text-muted-foreground">
                  {emailVerificationSetting.description ||
                    "Users must verify their email address before logging in"}
                </p>
              </div>
              <Switch
                id="email-verification"
                checked={emailVerificationEnabled}
                onCheckedChange={toggleEmailVerification}
                disabled={updating === "require_email_verification"}
              />
            </div>
          ) : (
            <p className="text-muted-foreground">
              Email verification setting not found
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
