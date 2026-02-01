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
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Plus, Loader2, AlertCircle, Pencil } from "lucide-react";
import { toast } from "sonner";

interface Vendor {
  id: string;
  name: string;
  code: string | null;
  leadTimeDays: number;
}

interface Product {
  id: string;
  sku: string;
  name: string;
}

interface VendorProduct {
  id: string;
  vendorSku: string;
  vendorProductName: string | null;
  unitCost: number;
  currency: string;
  minOrderQty: number;
  orderMultiple: number;
  casePackQty: number | null;
  leadTimeDays: number | null;
  isPreferred: boolean;
  isActive: boolean;
  notes: string | null;
  vendor?: Vendor;
  product?: Product;
}

interface VendorProductDialogProps {
  // For creating: provide one of these
  productId?: string;
  vendorId?: string;
  // For editing: provide existing data
  existingData?: VendorProduct;
  // UI customization
  trigger?: React.ReactNode;
  onSuccess?: () => void;
}

export function VendorProductDialog({
  productId,
  vendorId,
  existingData,
  trigger,
  onSuccess,
}: VendorProductDialogProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // For selecting vendor/product if not provided
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loadingOptions, setLoadingOptions] = useState(false);

  const isEditing = !!existingData;

  const [formData, setFormData] = useState({
    productId: existingData?.product?.id || productId || "",
    vendorId: existingData?.vendor?.id || vendorId || "",
    vendorSku: existingData?.vendorSku || "",
    vendorProductName: existingData?.vendorProductName || "",
    unitCost: existingData?.unitCost?.toString() || "",
    currency: existingData?.currency || "USD",
    minOrderQty: existingData?.minOrderQty?.toString() || "1",
    orderMultiple: existingData?.orderMultiple?.toString() || "1",
    casePackQty: existingData?.casePackQty?.toString() || "",
    leadTimeDays: existingData?.leadTimeDays?.toString() || "",
    isPreferred: existingData?.isPreferred || false,
    isActive: existingData?.isActive ?? true,
    notes: existingData?.notes || "",
  });

  // Load vendors/products if needed
  useEffect(() => {
    if (open && !productId && !isEditing) {
      setLoadingOptions(true);
      fetch("/api/products?pageSize=100")
        .then((res) => res.json())
        .then((data) => setProducts(data.data || data))
        .catch(console.error)
        .finally(() => setLoadingOptions(false));
    }
    if (open && !vendorId && !isEditing) {
      fetch("/api/vendors")
        .then((res) => res.json())
        .then(setVendors)
        .catch(console.error);
    }
  }, [open, productId, vendorId, isEditing]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const payload = {
        productId: formData.productId,
        vendorId: formData.vendorId,
        vendorSku: formData.vendorSku,
        vendorProductName: formData.vendorProductName || undefined,
        unitCost: parseFloat(formData.unitCost),
        currency: formData.currency,
        minOrderQty: parseInt(formData.minOrderQty) || 1,
        orderMultiple: parseInt(formData.orderMultiple) || 1,
        casePackQty: formData.casePackQty ? parseInt(formData.casePackQty) : undefined,
        leadTimeDays: formData.leadTimeDays ? parseInt(formData.leadTimeDays) : undefined,
        isPreferred: formData.isPreferred,
        isActive: formData.isActive,
        notes: formData.notes || undefined,
      };

      const url = isEditing
        ? `/api/vendor-products/${existingData.id}`
        : "/api/vendor-products";
      const method = isEditing ? "PATCH" : "POST";

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || `Failed to ${isEditing ? "update" : "create"} vendor link`);
      }

      toast.success(isEditing ? "Vendor link updated" : "Vendor link created");
      setOpen(false);
      router.refresh();
      onSuccess?.();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  // Context-aware button label
  const addButtonLabel = vendorId ? "Add Product" : "Add Vendor";

  const defaultTrigger = isEditing ? (
    <Button variant="ghost" size="sm">
      <Pencil className="h-4 w-4" />
    </Button>
  ) : (
    <Button variant="outline" size="sm">
      <Plus className="h-4 w-4 mr-2" /> {addButtonLabel}
    </Button>
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger || defaultTrigger}</DialogTrigger>
      <DialogContent className="sm:max-w-[550px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {isEditing ? "Edit Vendor Link" : vendorId ? "Link Product to Vendor" : "Link Vendor to Product"}
            </DialogTitle>
            <DialogDescription>
              {isEditing
                ? "Update the sourcing details for this product-vendor relationship."
                : vendorId 
                  ? "Add a product that this vendor supplies with pricing and ordering details."
                  : "Add a vendor as a source for this product with pricing and ordering details."}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            {/* Product selector (if not provided) */}
            {!productId && !isEditing && (
              <div className="space-y-2">
                <Label htmlFor="productId">Product *</Label>
                <Select
                  value={formData.productId}
                  onValueChange={(value) => setFormData({ ...formData, productId: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={loadingOptions ? "Loading..." : "Select product"} />
                  </SelectTrigger>
                  <SelectContent>
                    {products.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.sku} - {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Vendor selector (if not provided) */}
            {!vendorId && !isEditing && (
              <div className="space-y-2">
                <Label htmlFor="vendorId">Vendor *</Label>
                <Select
                  value={formData.vendorId}
                  onValueChange={(value) => setFormData({ ...formData, vendorId: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select vendor" />
                  </SelectTrigger>
                  <SelectContent>
                    {vendors.map((v) => (
                      <SelectItem key={v.id} value={v.id}>
                        {v.name} {v.code ? `(${v.code})` : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="vendorSku">Vendor SKU *</Label>
                <Input
                  id="vendorSku"
                  value={formData.vendorSku}
                  onChange={(e) => setFormData({ ...formData, vendorSku: e.target.value })}
                  placeholder="Vendor's product code"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="vendorProductName">Vendor Product Name</Label>
                <Input
                  id="vendorProductName"
                  value={formData.vendorProductName}
                  onChange={(e) => setFormData({ ...formData, vendorProductName: e.target.value })}
                  placeholder="Name in vendor's catalog"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="unitCost">Unit Cost *</Label>
                <Input
                  id="unitCost"
                  type="number"
                  step="0.01"
                  value={formData.unitCost}
                  onChange={(e) => setFormData({ ...formData, unitCost: e.target.value })}
                  placeholder="0.00"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="currency">Currency</Label>
                <Select
                  value={formData.currency}
                  onValueChange={(value) => setFormData({ ...formData, currency: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="USD">USD</SelectItem>
                    <SelectItem value="EUR">EUR</SelectItem>
                    <SelectItem value="GBP">GBP</SelectItem>
                    <SelectItem value="CAD">CAD</SelectItem>
                    <SelectItem value="CNY">CNY</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="leadTimeDays">Lead Time (days)</Label>
                <Input
                  id="leadTimeDays"
                  type="number"
                  value={formData.leadTimeDays}
                  onChange={(e) => setFormData({ ...formData, leadTimeDays: e.target.value })}
                  placeholder="Use vendor default"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="minOrderQty">Min Order Qty</Label>
                <Input
                  id="minOrderQty"
                  type="number"
                  value={formData.minOrderQty}
                  onChange={(e) => setFormData({ ...formData, minOrderQty: e.target.value })}
                  placeholder="1"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="orderMultiple">Order Multiple</Label>
                <Input
                  id="orderMultiple"
                  type="number"
                  value={formData.orderMultiple}
                  onChange={(e) => setFormData({ ...formData, orderMultiple: e.target.value })}
                  placeholder="1"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="casePackQty">Case Pack Qty</Label>
                <Input
                  id="casePackQty"
                  type="number"
                  value={formData.casePackQty}
                  onChange={(e) => setFormData({ ...formData, casePackQty: e.target.value })}
                  placeholder="Units per case"
                />
              </div>
            </div>

            <div className="flex items-center gap-6">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="isPreferred"
                  checked={formData.isPreferred}
                  onCheckedChange={(checked) =>
                    setFormData({ ...formData, isPreferred: checked as boolean })
                  }
                />
                <Label htmlFor="isPreferred" className="font-normal">
                  Preferred vendor for this product
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="isActive"
                  checked={formData.isActive}
                  onCheckedChange={(checked) =>
                    setFormData({ ...formData, isActive: checked as boolean })
                  }
                />
                <Label htmlFor="isActive" className="font-normal">
                  Active
                </Label>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea
                id="notes"
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                placeholder="Any notes about sourcing from this vendor..."
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
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditing ? "Save Changes" : vendorId ? "Link Product" : "Link Vendor"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
