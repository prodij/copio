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
import { Pencil, Loader2, AlertCircle } from "lucide-react";
import { toast } from "sonner";

interface PurchaseOrder {
  id: string;
  poNumber: string;
  status: string;
  notes: string | null;
  expectedAt: string | null;
  tax: number | null;
  shipping: number | null;
  vendorOrderNumber: string | null;
  vendorInvoiceNumber: string | null;
}

interface EditPODialogProps {
  po: PurchaseOrder;
}

export function EditPODialog({ po }: EditPODialogProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    expectedAt: po.expectedAt ? po.expectedAt.split("T")[0] : "",
    tax: po.tax?.toString() || "",
    shipping: po.shipping?.toString() || "",
    vendorOrderNumber: po.vendorOrderNumber || "",
    vendorInvoiceNumber: po.vendorInvoiceNumber || "",
    notes: po.notes || "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const payload: Record<string, unknown> = {};
      
      if (formData.expectedAt) {
        payload.expectedAt = new Date(formData.expectedAt).toISOString();
      }
      if (formData.tax) {
        payload.tax = parseFloat(formData.tax);
      }
      if (formData.shipping) {
        payload.shipping = parseFloat(formData.shipping);
      }
      if (formData.vendorOrderNumber !== (po.vendorOrderNumber || "")) {
        payload.vendorOrderNumber = formData.vendorOrderNumber || null;
      }
      if (formData.vendorInvoiceNumber !== (po.vendorInvoiceNumber || "")) {
        payload.vendorInvoiceNumber = formData.vendorInvoiceNumber || null;
      }
      if (formData.notes !== (po.notes || "")) {
        payload.notes = formData.notes || null;
      }

      const res = await fetch(`/api/purchase-orders/${po.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to update purchase order");
      }

      toast.success("Purchase order updated");
      setOpen(false);
      router.refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Pencil className="h-4 w-4 mr-2" /> Edit
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Edit Purchase Order</DialogTitle>
            <DialogDescription>
              Update details for {po.poNumber}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="expectedAt">Expected Delivery Date</Label>
              <Input
                id="expectedAt"
                type="date"
                value={formData.expectedAt}
                onChange={(e) => setFormData({ ...formData, expectedAt: e.target.value })}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="tax">Tax ($)</Label>
                <Input
                  id="tax"
                  type="number"
                  step="0.01"
                  value={formData.tax}
                  onChange={(e) => setFormData({ ...formData, tax: e.target.value })}
                  placeholder="0.00"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="shipping">Shipping ($)</Label>
                <Input
                  id="shipping"
                  type="number"
                  step="0.01"
                  value={formData.shipping}
                  onChange={(e) => setFormData({ ...formData, shipping: e.target.value })}
                  placeholder="0.00"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="vendorOrderNumber">Vendor Order #</Label>
                <Input
                  id="vendorOrderNumber"
                  value={formData.vendorOrderNumber}
                  onChange={(e) => setFormData({ ...formData, vendorOrderNumber: e.target.value })}
                  placeholder="Vendor's order reference"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="vendorInvoiceNumber">Vendor Invoice #</Label>
                <Input
                  id="vendorInvoiceNumber"
                  value={formData.vendorInvoiceNumber}
                  onChange={(e) => setFormData({ ...formData, vendorInvoiceNumber: e.target.value })}
                  placeholder="Vendor's invoice number"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea
                id="notes"
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                placeholder="Internal notes about this order..."
                rows={3}
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
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Changes
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
