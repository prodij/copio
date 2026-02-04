"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Logo } from "@/components/logo";
import { ArrowRight, Building2, MapPin, CheckCircle, Loader2 } from "lucide-react";

// Constants from company settings
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

const LOCATION_TYPES = ["WAREHOUSE", "FBA", "THREEPEL"] as const;

// Schemas
const companySchema = z.object({
  company_name: z.string().min(1, "Company name is required").max(100, "Name too long"),
  country: z.string().min(1, "Country is required"),
  timezone: z.string().min(1, "Timezone is required"),
  base_currency: z.string().min(1, "Currency is required"),
});

const locationSchema = z.object({
  name: z.string().min(1, "Location name is required").max(100, "Name too long"),
  type: z.enum(LOCATION_TYPES),
  address: z.string().max(500, "Address too long").optional().or(z.literal("")),
});

type CompanyFormData = z.infer<typeof companySchema>;
type LocationFormData = z.infer<typeof locationSchema>;

function StepIndicator({ currentStep }: { currentStep: number }) {
  const steps = [
    { number: 1, label: "Company Info", icon: Building2 },
    { number: 2, label: "First Location", icon: MapPin },
    { number: 3, label: "Complete", icon: CheckCircle },
  ];

  return (
    <div className="flex items-center justify-center gap-2 mb-8">
      {steps.map((step, index) => (
        <div key={step.number} className="flex items-center">
          <div
            className={`flex items-center justify-center w-8 h-8 rounded-full border-2 transition-colors ${
              currentStep >= step.number
                ? "bg-primary border-primary text-primary-foreground"
                : "border-muted-foreground/30 text-muted-foreground"
            }`}
          >
            {currentStep > step.number ? (
              <CheckCircle className="h-4 w-4" />
            ) : (
              <span className="text-sm font-medium">{step.number}</span>
            )}
          </div>
          {index < steps.length - 1 && (
            <div
              className={`w-12 h-0.5 mx-2 transition-colors ${
                currentStep > step.number ? "bg-primary" : "bg-muted-foreground/30"
              }`}
            />
          )}
        </div>
      ))}
    </div>
  );
}

function CompanyStep({
  onNext,
}: {
  onNext: () => void;
}) {
  const form = useForm<CompanyFormData>({
    resolver: zodResolver(companySchema),
    defaultValues: {
      company_name: "",
      country: "US",
      timezone: "America/Los_Angeles",
      base_currency: "USD",
    },
  });

  const onSubmit = async (data: CompanyFormData) => {
    try {
      const res = await fetch("/api/v1/company", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(data),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to save company info");
      }

      toast.success("Company info saved");
      onNext();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save company info");
    }
  };

  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="flex items-center justify-center gap-2 text-xl">
          <Building2 className="h-5 w-5" />
          Company Information
        </CardTitle>
        <CardDescription>
          Tell us about your business to get started
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="company_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Company Name *</FormLabel>
                  <FormControl>
                    <Input placeholder="Acme Corp" {...field} className="h-11" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="country"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Country *</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger className="h-11">
                        <SelectValue placeholder="Select country" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {COUNTRIES.map((c) => (
                        <SelectItem key={c.code} value={c.code}>
                          {c.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="timezone"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Timezone *</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger className="h-11">
                        <SelectValue placeholder="Select timezone" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {TIMEZONES.map((tz) => (
                        <SelectItem key={tz} value={tz}>
                          {tz.replace(/_/g, " ")}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="base_currency"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Base Currency *</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger className="h-11">
                        <SelectValue placeholder="Select currency" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {CURRENCIES.map((c) => (
                        <SelectItem key={c} value={c}>
                          {c}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="pt-4">
              <Button type="submit" className="w-full h-11" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <ArrowRight className="mr-2 h-4 w-4" />
                )}
                Continue
              </Button>
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}

function LocationStep({
  onNext,
}: {
  onNext: () => void;
}) {
  const form = useForm<LocationFormData>({
    resolver: zodResolver(locationSchema),
    defaultValues: {
      name: "",
      type: "WAREHOUSE",
      address: "",
    },
  });

  const onSubmit = async (data: LocationFormData) => {
    try {
      const payload = {
        name: data.name.trim(),
        type: data.type,
        address: data.address ? { street: data.address } : undefined,
      };

      const res = await fetch("/api/v1/locations/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create location");
      }

      toast.success("Location created");
      onNext();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create location");
    }
  };

  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="flex items-center justify-center gap-2 text-xl">
          <MapPin className="h-5 w-5" />
          Create Your First Location
        </CardTitle>
        <CardDescription>
          Set up a warehouse or storage location for your inventory
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Location Name *</FormLabel>
                  <FormControl>
                    <Input placeholder="Main Warehouse" {...field} className="h-11" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Type *</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger className="h-11">
                        <SelectValue placeholder="Select a type" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {LOCATION_TYPES.map((t) => (
                        <SelectItem key={t} value={t}>
                          {t === "THREEPEL" ? "3PL" : t}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="address"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Address (optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="123 Main St, City, State" {...field} className="h-11" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="pt-4">
              <Button type="submit" className="w-full h-11" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <ArrowRight className="mr-2 h-4 w-4" />
                )}
                Continue
              </Button>
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}

function CompleteStep() {
  const router = useRouter();
  const [isCompleting, setIsCompleting] = useState(false);

  const handleComplete = async () => {
    setIsCompleting(true);
    try {
      const res = await fetch("/api/v1/company/complete-onboarding", {
        method: "POST",
        credentials: "include",
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to complete onboarding");
      }

      toast.success("Welcome to Copio!");
      router.push("/");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to complete onboarding");
      setIsCompleting(false);
    }
  };

  return (
    <Card>
      <CardHeader className="text-center">
        <div className="flex justify-center mb-4">
          <div className="h-16 w-16 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
            <CheckCircle className="h-8 w-8 text-green-600 dark:text-green-400" />
          </div>
        </div>
        <CardTitle className="text-xl">You&apos;re All Set!</CardTitle>
        <CardDescription>
          Your workspace is ready. Start managing your inventory across all your sales channels.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="bg-muted/50 rounded-lg p-4 space-y-3">
          <h4 className="font-medium text-sm">What you can do next:</h4>
          <ul className="text-sm text-muted-foreground space-y-2">
            <li className="flex items-start gap-2">
              <span className="text-primary">1.</span>
              Add your products to the catalog
            </li>
            <li className="flex items-start gap-2">
              <span className="text-primary">2.</span>
              Connect your sales channels (Amazon, Shopify, etc.)
            </li>
            <li className="flex items-start gap-2">
              <span className="text-primary">3.</span>
              Set up vendors and start creating purchase orders
            </li>
          </ul>
        </div>

        <Button
          onClick={handleComplete}
          className="w-full h-11"
          disabled={isCompleting}
        >
          {isCompleting ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <ArrowRight className="mr-2 h-4 w-4" />
          )}
          Go to Dashboard
        </Button>
      </CardContent>
    </Card>
  );
}

export default function OnboardingPage() {
  const [step, setStep] = useState(1);

  return (
    <div className="space-y-6">
      {/* Logo */}
      <div className="flex justify-center">
        <Logo size="lg" />
      </div>

      {/* Progress indicator */}
      <StepIndicator currentStep={step} />

      {/* Step content */}
      {step === 1 && <CompanyStep onNext={() => setStep(2)} />}
      {step === 2 && <LocationStep onNext={() => setStep(3)} />}
      {step === 3 && <CompleteStep />}
    </div>
  );
}
