"use client";

import { useState, useEffect } from "react";
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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Loader2, AlertCircle, Package } from "lucide-react";

interface Vendor {
  id: string;
  name: string;
  code: string | null;
  leadTimeDays: number;
  _count: { products: number };
}

interface Location {
  id: string;
  name: string;
  type: string;
}

export function CreatePODialog() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loadingOptions, setLoadingOptions] = useState(false);

  const [formData, setFormData] = useState({
    vendorId: "",
    destinationId: "",
    notes: "",
    includeAllProducts: true,
  });

  // Load vendors and locations when dialog opens
  useEffect(() => {
    if (open) {
      setLoadingOptions(true);
      Promise.all([
        fetch("/api/vendors").then((res) => res.json()),
        fetch("/api/locations").then((res) => res.json()),
      ])
        .then(([vendorsData, locationsData]) => {
          setVendors(vendorsData);
          setLocations(locationsData);
        })
        .catch(console.error)
        .finally(() => setLoadingOptions(false));
    }
  }, [open]);

  const selectedVendor = vendors.find((v) => v.id === formData.vendorId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Use the quick-create endpoint that auto-populates from vendor products
      const res = await fetch(`/api/purchase-orders/from-vendor/${formData.vendorId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          destinationId: formData.destinationId,
          notes: formData.notes || undefined,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to create purchase order");
      }

      const po = await res.json();
      setOpen(false);
      router.push(`/purchase-orders/${po.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateEmpty = async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/purchase-orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vendorId: formData.vendorId,
          destinationId: formData.destinationId,
          notes: formData.notes || undefined,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to create purchase order");
      }

      const po = await res.json();
      setOpen(false);
      router.push(`/purchase-orders/${po.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Purchase Order
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create Purchase Order</DialogTitle>
            <DialogDescription>
              Start a new order to replenish inventory from a vendor.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="vendorId">Vendor *</Label>
              <Select
                value={formData.vendorId}
                onValueChange={(value) => setFormData({ ...formData, vendorId: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder={loadingOptions ? "Loading..." : "Select vendor"} />
                </SelectTrigger>
                <SelectContent>
                  {vendors.map((v) => (
                    <SelectItem key={v.id} value={v.id}>
                      <div className="flex items-center gap-2">
                        <span>{v.name}</span>
                        {v.code && <span className="text-muted-foreground">({v.code})</span>}
                        <span className="text-xs text-muted-foreground">
                          • {v._count.products} products
                        </span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedVendor && (
                <p className="text-sm text-muted-foreground">
                  Lead time: {selectedVendor.leadTimeDays} days • {selectedVendor._count.products} linked products
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="destinationId">Destination *</Label>
              <Select
                value={formData.destinationId}
                onValueChange={(value) => setFormData({ ...formData, destinationId: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select destination" />
                </SelectTrigger>
                <SelectContent>
                  {locations.map((l) => (
                    <SelectItem key={l.id} value={l.id}>
                      {l.name} ({l.type})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea
                id="notes"
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                placeholder="Any notes for this order..."
                rows={2}
              />
            </div>

            {selectedVendor && selectedVendor._count.products > 0 && (
              <div className="rounded-lg border bg-muted/50 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Package className="h-4 w-4" />
                  <span className="font-medium">Quick Start</span>
                </div>
                <p className="text-sm text-muted-foreground mb-3">
                  Auto-populate with all {selectedVendor._count.products} products from this vendor
                  at their minimum order quantities.
                </p>
              </div>
            )}
          </div>

          {error && (
            <div className="flex items-center gap-2 text-sm text-destructive mb-4">
              <AlertCircle className="h-4 w-4" />
              <span>{error}</span>
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-0">
            {selectedVendor && selectedVendor._count.products > 0 ? (
              <>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleCreateEmpty}
                  disabled={loading || !formData.vendorId || !formData.destinationId}
                >
                  Create Empty
                </Button>
                <Button
                  type="submit"
                  disabled={loading || !formData.vendorId || !formData.destinationId}
                >
                  {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Create with Products
                </Button>
              </>
            ) : (
              <Button
                type="button"
                onClick={handleCreateEmpty}
                disabled={loading || !formData.vendorId || !formData.destinationId}
              >
                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create PO
              </Button>
            )}
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
