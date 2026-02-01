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
import { Plus, Loader2, AlertCircle, Pencil } from "lucide-react";
import { toast } from "sonner";

interface ChannelListing {
  id: string;
  channel: string;
  channelSku: string;
  channelProductId: string | null;
  title: string | null;
  description: string | null;
  bulletPoints: string[];
  price: number | null;
  compareAtPrice: number | null;
  fulfillmentChannel: string;
  bufferStock: number;
  maxQuantity: number | null;
  handlingDays: number | null;
  status: string;
  listingUrl: string | null;
}

interface ChannelListingDialogProps {
  productId?: string;
  existingData?: ChannelListing;
  trigger?: React.ReactNode;
  onSuccess?: () => void;
}

const CHANNELS = [
  { value: "AMAZON", label: "Amazon" },
  { value: "SHOPIFY", label: "Shopify" },
  { value: "WALMART", label: "Walmart" },
  { value: "EBAY", label: "eBay" },
];

const FULFILLMENT_CHANNELS = [
  { value: "MERCHANT", label: "Merchant Fulfilled" },
  { value: "MARKETPLACE", label: "Marketplace (FBA/WFS)" },
  { value: "DROPSHIP", label: "Dropship" },
  { value: "THREEPEL", label: "3PL" },
];

const STATUSES = [
  { value: "DRAFT", label: "Draft" },
  { value: "PENDING", label: "Pending" },
  { value: "ACTIVE", label: "Active" },
  { value: "INACTIVE", label: "Inactive" },
];

export function ChannelListingDialog({
  productId,
  existingData,
  trigger,
  onSuccess,
}: ChannelListingDialogProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEditing = !!existingData;

  const [formData, setFormData] = useState({
    channel: existingData?.channel || "",
    channelSku: existingData?.channelSku || "",
    channelProductId: existingData?.channelProductId || "",
    title: existingData?.title || "",
    description: existingData?.description || "",
    price: existingData?.price?.toString() || "",
    compareAtPrice: existingData?.compareAtPrice?.toString() || "",
    fulfillmentChannel: existingData?.fulfillmentChannel || "MERCHANT",
    bufferStock: existingData?.bufferStock?.toString() || "0",
    maxQuantity: existingData?.maxQuantity?.toString() || "",
    handlingDays: existingData?.handlingDays?.toString() || "",
    status: existingData?.status || "DRAFT",
    listingUrl: existingData?.listingUrl || "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const payload = {
        productId: productId,
        channel: formData.channel,
        channelSku: formData.channelSku,
        channelProductId: formData.channelProductId || undefined,
        title: formData.title || undefined,
        description: formData.description || undefined,
        price: formData.price ? parseFloat(formData.price) : undefined,
        compareAtPrice: formData.compareAtPrice ? parseFloat(formData.compareAtPrice) : undefined,
        fulfillmentChannel: formData.fulfillmentChannel,
        bufferStock: parseInt(formData.bufferStock) || 0,
        maxQuantity: formData.maxQuantity ? parseInt(formData.maxQuantity) : undefined,
        handlingDays: formData.handlingDays ? parseInt(formData.handlingDays) : undefined,
        status: formData.status,
        listingUrl: formData.listingUrl || undefined,
      };

      const url = isEditing
        ? `/api/channel-listings/${existingData.id}`
        : "/api/channel-listings";
      const method = isEditing ? "PATCH" : "POST";

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || `Failed to ${isEditing ? "update" : "create"} listing`);
      }

      toast.success(isEditing ? "Listing updated" : "Listing created");
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

  const defaultTrigger = isEditing ? (
    <Button variant="ghost" size="sm">
      <Pencil className="h-4 w-4" />
    </Button>
  ) : (
    <Button variant="outline" size="sm">
      <Plus className="h-4 w-4 mr-2" /> Add Channel
    </Button>
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger || defaultTrigger}</DialogTrigger>
      <DialogContent className="sm:max-w-[550px] max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{isEditing ? "Edit Channel Listing" : "Add Channel Listing"}</DialogTitle>
            <DialogDescription>
              {isEditing
                ? "Update this marketplace listing."
                : "Create a listing for this product on a sales channel."}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="channel">Channel *</Label>
                <Select
                  value={formData.channel}
                  onValueChange={(value) => setFormData({ ...formData, channel: value })}
                  disabled={isEditing}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select channel" />
                  </SelectTrigger>
                  <SelectContent>
                    {CHANNELS.map((ch) => (
                      <SelectItem key={ch.value} value={ch.value}>
                        {ch.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="channelSku">Channel SKU *</Label>
                <Input
                  id="channelSku"
                  value={formData.channelSku}
                  onChange={(e) => setFormData({ ...formData, channelSku: e.target.value })}
                  placeholder="SKU on this channel"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="channelProductId">Channel Product ID</Label>
                <Input
                  id="channelProductId"
                  value={formData.channelProductId}
                  onChange={(e) => setFormData({ ...formData, channelProductId: e.target.value })}
                  placeholder="ASIN, Listing ID, etc."
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="status">Status</Label>
                <Select
                  value={formData.status}
                  onValueChange={(value) => setFormData({ ...formData, status: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STATUSES.map((s) => (
                      <SelectItem key={s.value} value={s.value}>
                        {s.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="title">Listing Title</Label>
              <Input
                id="title"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="Leave empty to use product name"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Channel-specific description (optional)"
                rows={3}
              />
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="price">Price ($)</Label>
                <Input
                  id="price"
                  type="number"
                  step="0.01"
                  value={formData.price}
                  onChange={(e) => setFormData({ ...formData, price: e.target.value })}
                  placeholder="0.00"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="compareAtPrice">Compare At ($)</Label>
                <Input
                  id="compareAtPrice"
                  type="number"
                  step="0.01"
                  value={formData.compareAtPrice}
                  onChange={(e) => setFormData({ ...formData, compareAtPrice: e.target.value })}
                  placeholder="MSRP"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="fulfillmentChannel">Fulfillment</Label>
                <Select
                  value={formData.fulfillmentChannel}
                  onValueChange={(value) => setFormData({ ...formData, fulfillmentChannel: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {FULFILLMENT_CHANNELS.map((fc) => (
                      <SelectItem key={fc.value} value={fc.value}>
                        {fc.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="bufferStock">Buffer Stock</Label>
                <Input
                  id="bufferStock"
                  type="number"
                  value={formData.bufferStock}
                  onChange={(e) => setFormData({ ...formData, bufferStock: e.target.value })}
                  placeholder="0"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="maxQuantity">Max Quantity</Label>
                <Input
                  id="maxQuantity"
                  type="number"
                  value={formData.maxQuantity}
                  onChange={(e) => setFormData({ ...formData, maxQuantity: e.target.value })}
                  placeholder="No limit"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="handlingDays">Handling Days</Label>
                <Input
                  id="handlingDays"
                  type="number"
                  value={formData.handlingDays}
                  onChange={(e) => setFormData({ ...formData, handlingDays: e.target.value })}
                  placeholder="0"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="listingUrl">Listing URL</Label>
              <Input
                id="listingUrl"
                value={formData.listingUrl}
                onChange={(e) => setFormData({ ...formData, listingUrl: e.target.value })}
                placeholder="https://..."
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
            <Button type="submit" disabled={loading || !formData.channel || !formData.channelSku}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditing ? "Save Changes" : "Create Listing"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
