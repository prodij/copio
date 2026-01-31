"use client";

import { useState } from "react";
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
import { Input } from "@/components/ui/input";
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
import { Plus, Loader2 } from "lucide-react";

const productSchema = z.object({
  name: z.string().min(1, "Product name is required").max(200, "Name too long"),
  sku: z
    .string()
    .min(1, "SKU is required")
    .max(50, "SKU too long")
    .regex(/^[A-Za-z0-9\-_]+$/, "SKU can only contain letters, numbers, hyphens and underscores"),
  brand: z.string().max(100, "Brand name too long").optional().or(z.literal("")),
  manufacturer: z.string().max(100, "Manufacturer name too long").optional().or(z.literal("")),
  shortDescription: z.string().max(500, "Description too long").optional().or(z.literal("")),
  upc: z
    .string()
    .regex(/^(\d{12}|\d{13})?$/, "UPC must be 12 or 13 digits")
    .optional()
    .or(z.literal("")),
  costPrice: z
    .string()
    .refine((val) => val === "" || (!isNaN(parseFloat(val)) && parseFloat(val) >= 0), {
      message: "Cost must be a positive number",
    })
    .optional()
    .or(z.literal("")),
  msrp: z
    .string()
    .refine((val) => val === "" || (!isNaN(parseFloat(val)) && parseFloat(val) >= 0), {
      message: "MSRP must be a positive number",
    })
    .optional()
    .or(z.literal("")),
  status: z.enum(["DRAFT", "ACTIVE"]),
});

type ProductFormData = z.infer<typeof productSchema>;

export function CreateProductDialog() {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  const form = useForm<ProductFormData>({
    resolver: zodResolver(productSchema),
    defaultValues: {
      name: "",
      sku: "",
      brand: "",
      manufacturer: "",
      shortDescription: "",
      upc: "",
      costPrice: "",
      msrp: "",
      status: "DRAFT",
    },
  });

  const onSubmit = async (data: ProductFormData) => {
    try {
      const payload = {
        name: data.name,
        sku: data.sku,
        status: data.status,
        brand: data.brand || undefined,
        manufacturer: data.manufacturer || undefined,
        shortDescription: data.shortDescription || undefined,
        upc: data.upc || undefined,
        costPrice: data.costPrice ? parseFloat(data.costPrice) : undefined,
        msrp: data.msrp ? parseFloat(data.msrp) : undefined,
      };

      const res = await fetch("/api/products", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Failed to create product");
      }

      const product = await res.json();
      toast.success("Product created successfully");
      form.reset();
      setOpen(false);
      router.push(`/products/${product.id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create product");
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Product
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px]">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <DialogHeader>
              <DialogTitle>Create Product</DialogTitle>
              <DialogDescription>
                Add a new product to your catalog. You can add more details after creation.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Product Name *</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., Wireless Bluetooth Headphones" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="sku"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>SKU *</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., WBH-001" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid grid-cols-3 gap-4">
                <FormField
                  control={form.control}
                  name="brand"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Brand</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., Acme" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="manufacturer"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Manufacturer</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., Acme Corp" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="upc"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>UPC</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., 012345678901" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="shortDescription"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Short Description</FormLabel>
                    <FormControl>
                      <Textarea placeholder="Brief product summary..." rows={2} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-3 gap-4">
                <FormField
                  control={form.control}
                  name="costPrice"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Cost Price ($)</FormLabel>
                      <FormControl>
                        <Input type="number" step="0.01" placeholder="0.00" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="msrp"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>MSRP ($)</FormLabel>
                      <FormControl>
                        <Input type="number" step="0.01" placeholder="0.00" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="status"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Status</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="DRAFT">Draft</SelectItem>
                          <SelectItem value="ACTIVE">Active</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create & Edit
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
