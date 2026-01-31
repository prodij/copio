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
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Plus, Loader2 } from "lucide-react";

const vendorSchema = z.object({
  name: z.string().min(1, "Vendor name is required").max(200, "Name too long"),
  code: z
    .string()
    .max(20, "Code too long")
    .regex(/^[A-Za-z0-9\-_]*$/, "Code can only contain letters, numbers, hyphens and underscores")
    .optional()
    .or(z.literal("")),
  leadTimeDays: z
    .string()
    .refine((val) => val === "" || (!isNaN(parseInt(val)) && parseInt(val) >= 0 && parseInt(val) <= 365), {
      message: "Lead time must be 0-365 days",
    }),
  minOrderValue: z
    .string()
    .refine((val) => val === "" || (!isNaN(parseFloat(val)) && parseFloat(val) >= 0), {
      message: "Min order must be a positive number",
    })
    .optional()
    .or(z.literal("")),
  paymentTerms: z.string().max(100, "Payment terms too long").optional().or(z.literal("")),
  notes: z.string().max(1000, "Notes too long").optional().or(z.literal("")),
});

type VendorFormData = z.infer<typeof vendorSchema>;

export function CreateVendorDialog() {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  const form = useForm<VendorFormData>({
    resolver: zodResolver(vendorSchema),
    defaultValues: {
      name: "",
      code: "",
      leadTimeDays: "14",
      minOrderValue: "",
      paymentTerms: "",
      notes: "",
    },
  });

  const onSubmit = async (data: VendorFormData) => {
    try {
      const payload = {
        name: data.name,
        code: data.code || undefined,
        leadTimeDays: parseInt(data.leadTimeDays) || 14,
        minOrderValue: data.minOrderValue ? parseFloat(data.minOrderValue) : undefined,
        paymentTerms: data.paymentTerms || undefined,
        notes: data.notes || undefined,
      };

      const res = await fetch("/api/vendors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Failed to create vendor");
      }

      const vendor = await res.json();
      toast.success("Vendor created successfully");
      form.reset();
      setOpen(false);
      router.push(`/vendors/${vendor.id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create vendor");
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Vendor
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <DialogHeader>
              <DialogTitle>Add Vendor</DialogTitle>
              <DialogDescription>
                Add a new supplier to your vendor directory.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Vendor Name *</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., Acme Supplies" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="code"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Vendor Code</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., ACME" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="leadTimeDays"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Lead Time (days)</FormLabel>
                      <FormControl>
                        <Input type="number" placeholder="14" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="minOrderValue"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Min Order Value ($)</FormLabel>
                      <FormControl>
                        <Input type="number" step="0.01" placeholder="0.00" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="paymentTerms"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Payment Terms</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., Net 30, 2/10 Net 30" {...field} />
                    </FormControl>
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
                        placeholder="Any additional notes about this vendor..."
                        rows={2}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create Vendor
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
