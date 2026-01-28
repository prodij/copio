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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Truck, Loader2, AlertCircle, ExternalLink } from "lucide-react";

interface PurchaseOrder {
  id: string;
  poNumber: string;
  carrier: string | null;
  trackingNumber: string | null;
  trackingUrl: string | null;
  shipmentStatus: string | null;
  vendorOrderNumber: string | null;
  vendorInvoiceNumber: string | null;
}

const CARRIERS = [
  { value: "UPS", label: "UPS" },
  { value: "FEDEX", label: "FedEx" },
  { value: "USPS", label: "USPS" },
  { value: "DHL", label: "DHL" },
  { value: "OTHER", label: "Other" },
];

const SHIPMENT_STATUSES = [
  { value: "PENDING", label: "Pending" },
  { value: "LABEL_CREATED", label: "Label Created" },
  { value: "IN_TRANSIT", label: "In Transit" },
  { value: "OUT_FOR_DELIVERY", label: "Out for Delivery" },
  { value: "DELIVERED", label: "Delivered" },
  { value: "EXCEPTION", label: "Exception" },
];

export function TrackingDialog({ po }: { po: PurchaseOrder }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    carrier: po.carrier || "",
    trackingNumber: po.trackingNumber || "",
    trackingUrl: po.trackingUrl || "",
    shipmentStatus: po.shipmentStatus || "",
    vendorOrderNumber: po.vendorOrderNumber || "",
    vendorInvoiceNumber: po.vendorInvoiceNumber || "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`/api/purchase-orders/${po.id}/tracking`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          carrier: formData.carrier || undefined,
          trackingNumber: formData.trackingNumber || undefined,
          trackingUrl: formData.trackingUrl || undefined,
          shipmentStatus: formData.shipmentStatus || undefined,
          vendorOrderNumber: formData.vendorOrderNumber || undefined,
          vendorInvoiceNumber: formData.vendorInvoiceNumber || undefined,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to update tracking");
      }

      setOpen(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Truck className="h-4 w-4 mr-2" />
          {po.trackingNumber ? "Update Tracking" : "Add Tracking"}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Shipping & Tracking</DialogTitle>
            <DialogDescription>
              Track the shipment for {po.poNumber}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="carrier">Carrier</Label>
                <Select
                  value={formData.carrier}
                  onValueChange={(value) => setFormData({ ...formData, carrier: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select carrier" />
                  </SelectTrigger>
                  <SelectContent>
                    {CARRIERS.map((c) => (
                      <SelectItem key={c.value} value={c.value}>
                        {c.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="shipmentStatus">Shipment Status</Label>
                <Select
                  value={formData.shipmentStatus}
                  onValueChange={(value) => setFormData({ ...formData, shipmentStatus: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select status" />
                  </SelectTrigger>
                  <SelectContent>
                    {SHIPMENT_STATUSES.map((s) => (
                      <SelectItem key={s.value} value={s.value}>
                        {s.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="trackingNumber">Tracking Number</Label>
              <Input
                id="trackingNumber"
                value={formData.trackingNumber}
                onChange={(e) => setFormData({ ...formData, trackingNumber: e.target.value })}
                placeholder="1Z999AA10123456784"
              />
              <p className="text-xs text-muted-foreground">
                Tracking URL will be auto-generated for UPS, FedEx, USPS, DHL
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="trackingUrl">Tracking URL (optional)</Label>
              <div className="flex gap-2">
                <Input
                  id="trackingUrl"
                  value={formData.trackingUrl}
                  onChange={(e) => setFormData({ ...formData, trackingUrl: e.target.value })}
                  placeholder="https://..."
                  className="flex-1"
                />
                {formData.trackingUrl && (
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => window.open(formData.trackingUrl, "_blank")}
                  >
                    <ExternalLink className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="vendorOrderNumber">Vendor Order #</Label>
                <Input
                  id="vendorOrderNumber"
                  value={formData.vendorOrderNumber}
                  onChange={(e) => setFormData({ ...formData, vendorOrderNumber: e.target.value })}
                  placeholder="Vendor's reference"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="vendorInvoiceNumber">Vendor Invoice #</Label>
                <Input
                  id="vendorInvoiceNumber"
                  value={formData.vendorInvoiceNumber}
                  onChange={(e) => setFormData({ ...formData, vendorInvoiceNumber: e.target.value })}
                  placeholder="Invoice number"
                />
              </div>
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
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Tracking
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
