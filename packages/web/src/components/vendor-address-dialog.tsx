"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Plus, Loader2, AlertCircle, Pencil, MapPin } from "lucide-react";

interface VendorAddress {
  id: string;
  type: string;
  label: string | null;
  isPrimary: boolean;
  street1: string;
  street2: string | null;
  city: string;
  state: string | null;
  postalCode: string | null;
  country: string;
  contactName: string | null;
  contactPhone: string | null;
  contactEmail: string | null;
  shippingNotes: string | null;
}

interface VendorAddressDialogProps {
  vendorId: string;
  existingData?: VendorAddress;
  trigger?: React.ReactNode;
  onSuccess?: () => void;
}

const ADDRESS_TYPES = [
  { value: "CORPORATE", label: "Corporate HQ" },
  { value: "WAREHOUSE", label: "Warehouse" },
  { value: "MANUFACTURING", label: "Manufacturing" },
  { value: "RETURNS", label: "Returns" },
  { value: "BILLING", label: "Billing" },
];

const COUNTRIES = [
  { value: "US", label: "United States" },
  { value: "CN", label: "China" },
  { value: "MX", label: "Mexico" },
  { value: "CA", label: "Canada" },
  { value: "TW", label: "Taiwan" },
  { value: "VN", label: "Vietnam" },
  { value: "IN", label: "India" },
  { value: "KR", label: "South Korea" },
  { value: "JP", label: "Japan" },
  { value: "DE", label: "Germany" },
  { value: "GB", label: "United Kingdom" },
];

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3002";

export function VendorAddressDialog({
  vendorId,
  existingData,
  trigger,
  onSuccess,
}: VendorAddressDialogProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEditing = !!existingData;

  const [formData, setFormData] = useState({
    type: existingData?.type || "WAREHOUSE",
    label: existingData?.label || "",
    isPrimary: existingData?.isPrimary || false,
    street1: existingData?.street1 || "",
    street2: existingData?.street2 || "",
    city: existingData?.city || "",
    state: existingData?.state || "",
    postalCode: existingData?.postalCode || "",
    country: existingData?.country || "US",
    contactName: existingData?.contactName || "",
    contactPhone: existingData?.contactPhone || "",
    contactEmail: existingData?.contactEmail || "",
    shippingNotes: existingData?.shippingNotes || "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const payload = {
        vendorId,
        type: formData.type,
        label: formData.label || undefined,
        isPrimary: formData.isPrimary,
        street1: formData.street1,
        street2: formData.street2 || undefined,
        city: formData.city,
        state: formData.state || undefined,
        postalCode: formData.postalCode || undefined,
        country: formData.country,
        contactName: formData.contactName || undefined,
        contactPhone: formData.contactPhone || undefined,
        contactEmail: formData.contactEmail || undefined,
        shippingNotes: formData.shippingNotes || undefined,
      };

      const url = isEditing
        ? `${API_URL}/vendor-addresses/${existingData.id}`
        : `${API_URL}/vendor-addresses`;
      const method = isEditing ? "PATCH" : "POST";

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || `Failed to ${isEditing ? "update" : "create"} address`);
      }

      setOpen(false);
      router.refresh();
      onSuccess?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const defaultTrigger = isEditing ? (
    <Button variant="ghost" size="sm">
      <Pencil className="h-4 w-4" />
    </Button>
  ) : (
    <Button variant="outline" size="sm">
      <MapPin className="h-4 w-4 mr-2" /> Add Address
    </Button>
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger || defaultTrigger}</DialogTrigger>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{isEditing ? "Edit Address" : "Add Address"}</DialogTitle>
            <DialogDescription>
              {isEditing ? "Update location details." : "Add a warehouse or office location."}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            {/* Type and Label */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="type">Address Type</Label>
                <Select
                  value={formData.type}
                  onValueChange={(value) => setFormData({ ...formData, type: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ADDRESS_TYPES.map((t) => (
                      <SelectItem key={t.value} value={t.value}>
                        {t.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="label">Label (optional)</Label>
                <Input
                  id="label"
                  value={formData.label}
                  onChange={(e) => setFormData({ ...formData, label: e.target.value })}
                  placeholder="West Coast DC"
                />
              </div>
            </div>

            {/* Street Address */}
            <div className="space-y-2">
              <Label htmlFor="street1">Street Address *</Label>
              <Input
                id="street1"
                value={formData.street1}
                onChange={(e) => setFormData({ ...formData, street1: e.target.value })}
                placeholder="123 Industrial Blvd"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="street2">Street Address 2</Label>
              <Input
                id="street2"
                value={formData.street2}
                onChange={(e) => setFormData({ ...formData, street2: e.target.value })}
                placeholder="Suite 100, Building A"
              />
            </div>

            {/* City, State, Postal */}
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="city">City *</Label>
                <Input
                  id="city"
                  value={formData.city}
                  onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                  placeholder="Los Angeles"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="state">State/Province</Label>
                <Input
                  id="state"
                  value={formData.state}
                  onChange={(e) => setFormData({ ...formData, state: e.target.value })}
                  placeholder="CA"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="postalCode">Postal Code</Label>
                <Input
                  id="postalCode"
                  value={formData.postalCode}
                  onChange={(e) => setFormData({ ...formData, postalCode: e.target.value })}
                  placeholder="90001"
                />
              </div>
            </div>

            {/* Country */}
            <div className="space-y-2">
              <Label htmlFor="country">Country *</Label>
              <Select
                value={formData.country}
                onValueChange={(value) => setFormData({ ...formData, country: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {COUNTRIES.map((c) => (
                    <SelectItem key={c.value} value={c.value}>
                      {c.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Location Contact */}
            <div className="border-t pt-4 mt-2">
              <p className="text-sm font-medium mb-3">Location Contact (optional)</p>
              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="contactName">Name</Label>
                  <Input
                    id="contactName"
                    value={formData.contactName}
                    onChange={(e) => setFormData({ ...formData, contactName: e.target.value })}
                    placeholder="John Doe"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="contactPhone">Phone</Label>
                  <Input
                    id="contactPhone"
                    value={formData.contactPhone}
                    onChange={(e) => setFormData({ ...formData, contactPhone: e.target.value })}
                    placeholder="(555) 123-4567"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="contactEmail">Email</Label>
                  <Input
                    id="contactEmail"
                    type="email"
                    value={formData.contactEmail}
                    onChange={(e) => setFormData({ ...formData, contactEmail: e.target.value })}
                    placeholder="john@vendor.com"
                  />
                </div>
              </div>
            </div>

            {/* Primary checkbox */}
            <div className="flex items-center space-x-2">
              <Checkbox
                id="isPrimary"
                checked={formData.isPrimary}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, isPrimary: checked as boolean })
                }
              />
              <Label htmlFor="isPrimary" className="font-normal">
                Primary {formData.type.toLowerCase()} address for this vendor
              </Label>
            </div>

            {/* Shipping Notes */}
            <div className="space-y-2">
              <Label htmlFor="shippingNotes">Shipping Notes</Label>
              <Textarea
                id="shippingNotes"
                value={formData.shippingNotes}
                onChange={(e) => setFormData({ ...formData, shippingNotes: e.target.value })}
                placeholder="Delivery hours, dock requirements, special instructions..."
                rows={2}
              />
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-sm text-destructive mb-4">
              <AlertCircle className="h-4 w-4" />
              <span>{error}</span>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading || !formData.street1 || !formData.city}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditing ? "Save Changes" : "Add Address"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
