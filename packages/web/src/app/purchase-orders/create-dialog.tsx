"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
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
import { Textarea } from "@/components/ui/textarea";
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
import { Plus, Loader2, Package } from "lucide-react";

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

const poSchema = z.object({
  vendorId: z.string().min(1, "Vendor is required"),
  destinationId: z.string().min(1, "Destination is required"),
  notes: z.string().max(1000, "Notes too long").optional().or(z.literal("")),
});

type POFormData = z.infer<typeof poSchema>;

export function CreatePODialog() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loadingOptions, setLoadingOptions] = useState(false);

  const form = useForm<POFormData>({
    resolver: zodResolver(poSchema),
    defaultValues: {
      vendorId: "",
      destinationId: "",
      notes: "",
    },
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
        .catch((err) => {
          console.error(err);
          toast.error("Failed to load vendors and locations");
        })
        .finally(() => setLoadingOptions(false));
    }
  }, [open]);

  const selectedVendor = vendors.find((v) => v.id === form.watch("vendorId"));

  const handleCreateWithProducts = async (data: POFormData) => {
    try {
      const res = await fetch(`/api/purchase-orders/from-vendor/${data.vendorId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          destinationId: data.destinationId,
          notes: data.notes || undefined,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Failed to create purchase order");
      }

      const po = await res.json();
      toast.success("Purchase order created with products");
      setOpen(false);
      router.push(`/purchase-orders/${po.id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Something went wrong");
    }
  };

  const handleCreateEmpty = async () => {
    const data = form.getValues();
    if (!form.formState.isValid) {
      await form.trigger();
      return;
    }

    try {
      const res = await fetch("/api/purchase-orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vendorId: data.vendorId,
          destinationId: data.destinationId,
          notes: data.notes || undefined,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Failed to create purchase order");
      }

      const po = await res.json();
      toast.success("Empty purchase order created");
      setOpen(false);
      router.push(`/purchase-orders/${po.id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Something went wrong");
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
        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleCreateWithProducts)}>
            <DialogHeader>
              <DialogTitle>Create Purchase Order</DialogTitle>
              <DialogDescription>
                Start a new order to replenish inventory from a vendor.
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="vendorId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Vendor *</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder={loadingOptions ? "Loading..." : "Select vendor"} />
                        </SelectTrigger>
                      </FormControl>
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
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="destinationId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Destination *</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select destination" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {locations.map((l) => (
                          <SelectItem key={l.id} value={l.id}>
                            {l.name} ({l.type})
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
                name="notes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Notes</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Any notes for this order..."
                        rows={2}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

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

            <DialogFooter className="gap-2 sm:gap-0">
              {selectedVendor && selectedVendor._count.products > 0 ? (
                <>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleCreateEmpty}
                    disabled={form.formState.isSubmitting || !form.watch("vendorId") || !form.watch("destinationId")}
                  >
                    Create Empty
                  </Button>
                  <Button
                    type="submit"
                    disabled={form.formState.isSubmitting || !form.watch("vendorId") || !form.watch("destinationId")}
                  >
                    {form.formState.isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Create with Products
                  </Button>
                </>
              ) : (
                <Button
                  type="button"
                  onClick={handleCreateEmpty}
                  disabled={form.formState.isSubmitting || !form.watch("vendorId") || !form.watch("destinationId")}
                >
                  {form.formState.isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Create PO
                </Button>
              )}
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
