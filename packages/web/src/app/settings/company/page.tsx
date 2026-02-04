"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Building2, MapPin, Phone, Globe, Save } from "lucide-react";
import { toast } from "sonner";

interface CompanyProfile {
  id: string;
  name: string;
  slug: string;
  timezone: string;
  base_currency: string;
  company_name: string | null;
  legal_name: string | null;
  tax_id: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  country: string | null;
  phone: string | null;
  email: string | null;
  website: string | null;
  logo_url: string | null;
}

const COUNTRIES = [
  { code: "US", name: "United States" },
  { code: "CA", name: "Canada" },
  { code: "MX", name: "Mexico" },
  { code: "GB", name: "United Kingdom" },
  { code: "DE", name: "Germany" },
  { code: "FR", name: "France" },
  { code: "CN", name: "China" },
  { code: "JP", name: "Japan" },
  { code: "KR", name: "South Korea" },
  { code: "AU", name: "Australia" },
];

const CURRENCIES = ["USD", "CAD", "EUR", "GBP", "CNY", "JPY", "KRW", "AUD", "MXN"];

const TIMEZONES = [
  "America/Los_Angeles",
  "America/Denver",
  "America/Chicago",
  "America/New_York",
  "America/Toronto",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Asia/Tokyo",
  "Asia/Seoul",
  "Asia/Shanghai",
  "Australia/Sydney",
];

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-72" />
        </CardHeader>
        <CardContent className="space-y-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-10 w-full" />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

export default function CompanySettingsPage() {
  const { isAuthenticated } = useAuth();
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState<Partial<CompanyProfile>>({});

  useEffect(() => {
    if (!isAuthenticated) return;

    fetch("/api/v1/company", {
      credentials: "include",
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data) {
          setProfile(data);
          setFormData(data);
        }
      })
      .finally(() => setLoading(false));
  }, [isAuthenticated]);

  const handleChange = (field: keyof CompanyProfile, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value || null }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch("/api/v1/company", {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(formData),
      });

      if (res.ok) {
        const updated = await res.json();
        setProfile(updated);
        toast.success("Company profile updated");
      } else {
        const err = await res.json();
        toast.error(err.detail || "Failed to save");
      }
    } catch {
      toast.error("Failed to save");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingSkeleton />;
  if (!profile) return <p>Failed to load company profile</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Company Settings</h1>
          <p className="text-muted-foreground">
            Configure your business details for POs, invoices, and documents
          </p>
        </div>
        <Button onClick={handleSave} disabled={saving}>
          <Save className="mr-2 h-4 w-4" />
          {saving ? "Saving..." : "Save Changes"}
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Business Identity */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5" />
              Business Identity
            </CardTitle>
            <CardDescription>
              Legal name and tax information
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="company_name">Company Name</Label>
              <Input
                id="company_name"
                                value={formData.company_name || ""}
                onChange={(e) => handleChange("company_name", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="legal_name">Legal Name (if different)</Label>
              <Input
                id="legal_name"
                                value={formData.legal_name || ""}
                onChange={(e) => handleChange("legal_name", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tax_id">Tax ID / EIN</Label>
              <Input
                id="tax_id"
                                value={formData.tax_id || ""}
                onChange={(e) => handleChange("tax_id", e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        {/* Address */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MapPin className="h-5 w-5" />
              Business Address
            </CardTitle>
            <CardDescription>
              Primary business location
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="address_line1">Address Line 1</Label>
              <Input
                id="address_line1"
                                value={formData.address_line1 || ""}
                onChange={(e) => handleChange("address_line1", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="address_line2">Address Line 2</Label>
              <Input
                id="address_line2"
                                value={formData.address_line2 || ""}
                onChange={(e) => handleChange("address_line2", e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="city">City</Label>
                <Input
                  id="city"
                                    value={formData.city || ""}
                  onChange={(e) => handleChange("city", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="state">State / Province</Label>
                <Input
                  id="state"
                                    value={formData.state || ""}
                  onChange={(e) => handleChange("state", e.target.value)}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="postal_code">Postal Code</Label>
                <Input
                  id="postal_code"
                                    value={formData.postal_code || ""}
                  onChange={(e) => handleChange("postal_code", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="country">Country</Label>
                <Select
                  value={formData.country || "US"}
                  onValueChange={(v) => handleChange("country", v)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {COUNTRIES.map((c) => (
                      <SelectItem key={c.code} value={c.code}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Contact */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Phone className="h-5 w-5" />
              Contact Information
            </CardTitle>
            <CardDescription>
              How vendors and partners can reach you
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                type="tel"
                                value={formData.phone || ""}
                onChange={(e) => handleChange("phone", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Business Email</Label>
              <Input
                id="email"
                type="email"
                                value={formData.email || ""}
                onChange={(e) => handleChange("email", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="website">Website</Label>
              <Input
                id="website"
                type="url"
                                value={formData.website || ""}
                onChange={(e) => handleChange("website", e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        {/* Regional Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-5 w-5" />
              Regional Settings
            </CardTitle>
            <CardDescription>
              Timezone and currency preferences
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="timezone">Timezone</Label>
              <Select
                value={formData.timezone || "America/Los_Angeles"}
                onValueChange={(v) => handleChange("timezone", v)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TIMEZONES.map((tz) => (
                    <SelectItem key={tz} value={tz}>
                      {tz.replace(/_/g, " ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="base_currency">Base Currency</Label>
              <Select
                value={formData.base_currency || "USD"}
                onValueChange={(v) => handleChange("base_currency", v)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CURRENCIES.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
