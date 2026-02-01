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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Loader2, AlertCircle } from "lucide-react";
import { toast } from "sonner";

interface VendorProduct {
  id: string;
  productId: string;
  vendorSku: string;
  unitCost: number;
  minOrderQty: number;
  product: { id: string; sku: string; name: string };
}

interface AddLineDialogProps {
  poId: string;
  vendorId: string;
}

export function AddLineDialog({ poId, vendorId }: AddLineDialogProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [vendorProducts, setVendorProducts] = useState<VendorProduct[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(false);

  const [formData, setFormData] = useState({
    productId: "",
    quantityOrdered: "",
    unitCost: "",
  });

  // Load vendor products when dialog opens
  useEffect(() => {
    if (open) {
      setLoadingProducts(true);
      fetch(`/api/vendor-products?vendorId=${vendorId}`)
        .then((res) => res.json())
        .then(setVendorProducts)
        .catch(console.error)
        .finally(() => setLoadingProducts(false));
    }
  }, [open, vendorId]);

  const selectedProduct = vendorProducts.find((vp) => vp.productId === formData.productId);

  // Auto-fill unit cost when product is selected
  useEffect(() => {
    if (selectedProduct && !formData.unitCost) {
      setFormData((prev) => ({
        ...prev,
        unitCost: selectedProduct.unitCost.toString(),
        quantityOrdered: prev.quantityOrdered || selectedProduct.minOrderQty.toString(),
      }));
    }
  }, [selectedProduct]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`/api/purchase-orders/${poId}/lines`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          productId: formData.productId,
          quantityOrdered: parseInt(formData.quantityOrdered),
          unitCost: parseFloat(formData.unitCost),
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to add line");
      }

      toast.success("Item added to purchase order");
      setFormData({ productId: "", quantityOrdered: "", unitCost: "" });
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
          <Plus className="h-4 w-4 mr-2" /> Add Item
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[450px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Add Item to PO</DialogTitle>
            <DialogDescription>
              Add a product from this vendor to the purchase order.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="productId">Product *</Label>
              <Select
                value={formData.productId}
                onValueChange={(value) => setFormData({ ...formData, productId: value, unitCost: "", quantityOrdered: "" })}
              >
                <SelectTrigger>
                  <SelectValue placeholder={loadingProducts ? "Loading..." : "Select product"} />
                </SelectTrigger>
                <SelectContent>
                  {vendorProducts.map((vp) => (
                    <SelectItem key={vp.productId} value={vp.productId}>
                      {vp.product.sku} - {vp.product.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedProduct && (
                <p className="text-sm text-muted-foreground">
                  Vendor SKU: {selectedProduct.vendorSku} • MOQ: {selectedProduct.minOrderQty}
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="quantityOrdered">Quantity *</Label>
                <Input
                  id="quantityOrdered"
                  type="number"
                  min="1"
                  value={formData.quantityOrdered}
                  onChange={(e) => setFormData({ ...formData, quantityOrdered: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="unitCost">Unit Cost ($) *</Label>
                <Input
                  id="unitCost"
                  type="number"
                  step="0.01"
                  value={formData.unitCost}
                  onChange={(e) => setFormData({ ...formData, unitCost: e.target.value })}
                  required
                />
              </div>
            </div>

            {formData.quantityOrdered && formData.unitCost && (
              <div className="text-sm text-muted-foreground">
                Line total: ${(parseFloat(formData.quantityOrdered) * parseFloat(formData.unitCost)).toFixed(2)}
              </div>
            )}
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
            <Button type="submit" disabled={loading || !formData.productId}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Add Item
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
