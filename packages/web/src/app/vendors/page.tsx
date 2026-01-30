import Link from "next/link";
import { Suspense } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { CreateVendorDialog } from "./create-dialog";
import { VendorFilters } from "@/components/vendor-filters";
import { SortableHeader } from "@/components/sortable-header";

const API_URL = process.env.API_URL || "http://localhost:3002";

interface Vendor {
  id: string;
  name: string;
  code: string | null;
  tier: string;
  contact: Record<string, unknown>;
  leadTimeDays: number;
  minOrderValue: number | null;
  paymentTerms: string | null;
  currency: string | null;
  isActive: boolean;
  createdAt: string;
  _count: { products: number; purchaseOrders: number };
}

async function getVendors(): Promise<Vendor[]> {
  const res = await fetch(`${API_URL}/vendors`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch vendors");
  return res.json();
}

const TIER_COLORS: Record<string, string> = {
  STRATEGIC: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
  PREFERRED: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  STANDARD: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
  PROBATIONARY: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
};

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

interface SearchParams {
  search?: string;
  tier?: string;
  status?: string;
  sortBy?: string;
  sortDir?: "asc" | "desc";
}

export default async function VendorsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const allVendors = await getVendors();
  
  // Filter vendors based on search params
  let vendors = allVendors;
  
  if (params.search) {
    const search = params.search.toLowerCase();
    vendors = vendors.filter(
      (v) =>
        v.name.toLowerCase().includes(search) ||
        (v.code && v.code.toLowerCase().includes(search))
    );
  }
  
  if (params.tier && params.tier !== "all") {
    vendors = vendors.filter((v) => v.tier === params.tier);
  }
  
  if (params.status && params.status !== "all") {
    const isActive = params.status === "active";
    vendors = vendors.filter((v) => v.isActive === isActive);
  }

  // Sort vendors
  const sortBy = params.sortBy || "name";
  const sortDir = params.sortDir || "asc";
  
  vendors.sort((a, b) => {
    let aVal: string | number | boolean | null;
    let bVal: string | number | boolean | null;
    
    switch (sortBy) {
      case "name":
        aVal = a.name.toLowerCase();
        bVal = b.name.toLowerCase();
        break;
      case "code":
        aVal = a.code?.toLowerCase() || "";
        bVal = b.code?.toLowerCase() || "";
        break;
      case "tier":
        const tierOrder = { STRATEGIC: 1, PREFERRED: 2, STANDARD: 3, PROBATIONARY: 4 };
        aVal = tierOrder[a.tier as keyof typeof tierOrder] || 5;
        bVal = tierOrder[b.tier as keyof typeof tierOrder] || 5;
        break;
      case "products":
        aVal = a._count.products;
        bVal = b._count.products;
        break;
      case "leadTimeDays":
        aVal = a.leadTimeDays;
        bVal = b.leadTimeDays;
        break;
      case "isActive":
        aVal = a.isActive ? 1 : 0;
        bVal = b.isActive ? 1 : 0;
        break;
      case "createdAt":
        aVal = a.createdAt;
        bVal = b.createdAt;
        break;
      default:
        return 0;
    }
    
    if (aVal === null || aVal === "") return sortDir === "asc" ? 1 : -1;
    if (bVal === null || bVal === "") return sortDir === "asc" ? -1 : 1;
    
    if (aVal < bVal) return sortDir === "asc" ? -1 : 1;
    if (aVal > bVal) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Vendors</h1>
          <p className="text-muted-foreground">Manage your suppliers and sourcing partners.</p>
        </div>
        <CreateVendorDialog />
      </div>

      <Suspense fallback={<div className="h-10" />}>
        <VendorFilters />
      </Suspense>

      <Card>
        <CardHeader>
          <CardTitle>Vendor Directory</CardTitle>
          <CardDescription>
            {vendors.length} of {allVendors.length} vendor{allVendors.length !== 1 ? "s" : ""}
            {vendors.length !== allVendors.length && " (filtered)"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <SortableHeader field="name">Vendor</SortableHeader>
                <SortableHeader field="code">Code</SortableHeader>
                <SortableHeader field="tier">Tier</SortableHeader>
                <SortableHeader field="products" className="text-center">Products</SortableHeader>
                <SortableHeader field="leadTimeDays" className="text-center">Lead Time</SortableHeader>
                <TableHead>Payment Terms</TableHead>
                <SortableHeader field="isActive">Status</SortableHeader>
                <SortableHeader field="createdAt">Added</SortableHeader>
              </TableRow>
            </TableHeader>
            <TableBody>
              {vendors.length > 0 ? (
                vendors.map((vendor) => (
                  <TableRow key={vendor.id} className="cursor-pointer hover:bg-muted/50">
                    <TableCell>
                      <Link href={`/vendors/${vendor.id}`} className="block">
                        <div className="font-medium hover:underline">{vendor.name}</div>
                      </Link>
                    </TableCell>
                    <TableCell className="font-mono text-sm">
                      {vendor.code || "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={TIER_COLORS[vendor.tier] || TIER_COLORS.STANDARD}>
                        {vendor.tier}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      {vendor._count.products}
                    </TableCell>
                    <TableCell className="text-center">
                      {vendor.leadTimeDays} days
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {vendor.paymentTerms || "—"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={vendor.isActive ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"}
                      >
                        {vendor.isActive ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(vendor.createdAt)}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                    No vendors found. {params.search || params.tier || params.status ? "Try adjusting your filters." : "Add your first vendor to start tracking sourcing."}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
