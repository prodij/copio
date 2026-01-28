import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Package, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const API_URL = process.env.API_URL || "http://localhost:3002";

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
  product: { id: string; sku: string; name: string };
}

interface Vendor {
  id: string;
  name: string;
  code: string | null;
  contact: Record<string, unknown>;
  address: Record<string, unknown>;
  leadTimeDays: number;
  minOrderValue: number | null;
  paymentTerms: string | null;
  currency: string | null;
  notes: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
  products: VendorProduct[];
  _count: { purchaseOrders: number };
}

async function getVendor(id: string): Promise<Vendor | null> {
  const res = await fetch(`${API_URL}/vendors/${id}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch vendor");
  return res.json();
}

export default async function VendorDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const vendor = await getVendor(id);

  if (!vendor) {
    notFound();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/vendors">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">{vendor.name}</h1>
            <Badge
              variant="outline"
              className={vendor.isActive ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"}
            >
              {vendor.isActive ? "Active" : "Inactive"}
            </Badge>
          </div>
          {vendor.code && <p className="text-muted-foreground">Code: {vendor.code}</p>}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Lead Time</CardDescription>
            <CardTitle className="text-2xl">{vendor.leadTimeDays} days</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Min Order</CardDescription>
            <CardTitle className="text-2xl">
              {vendor.minOrderValue ? `$${vendor.minOrderValue}` : "—"}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Products</CardDescription>
            <CardTitle className="text-2xl flex items-center gap-2">
              <Package className="h-5 w-5" />
              {vendor.products.length}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Purchase Orders</CardDescription>
            <CardTitle className="text-2xl flex items-center gap-2">
              <FileText className="h-5 w-5" />
              {vendor._count.purchaseOrders}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Vendor Details */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Vendor Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Payment Terms</p>
                <p className="font-medium">{vendor.paymentTerms || "Not specified"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Currency</p>
                <p className="font-medium">{vendor.currency || "USD"}</p>
              </div>
            </div>
            {vendor.notes && (
              <div>
                <p className="text-sm text-muted-foreground">Notes</p>
                <p className="text-sm">{vendor.notes}</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Contact Information</CardTitle>
          </CardHeader>
          <CardContent>
            {Object.keys(vendor.contact).length > 0 ? (
              <div className="space-y-2">
                {Object.entries(vendor.contact).map(([key, value]) => (
                  <div key={key}>
                    <p className="text-sm text-muted-foreground capitalize">{key}</p>
                    <p className="font-medium">{String(value)}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">No contact information added</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Products from this Vendor */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Products from this Vendor</CardTitle>
            <CardDescription>Products you source from {vendor.name}</CardDescription>
          </div>
          <Button variant="outline" size="sm">
            Add Product
          </Button>
        </CardHeader>
        <CardContent>
          {vendor.products.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead>Vendor SKU</TableHead>
                  <TableHead className="text-right">Unit Cost</TableHead>
                  <TableHead className="text-center">MOQ</TableHead>
                  <TableHead className="text-center">Order Multiple</TableHead>
                  <TableHead className="text-center">Case Pack</TableHead>
                  <TableHead className="text-center">Lead Time</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {vendor.products.map((vp) => (
                  <TableRow key={vp.id}>
                    <TableCell>
                      <Link href={`/products/${vp.product.id}`} className="hover:underline">
                        <div className="font-medium">{vp.product.name}</div>
                        <div className="text-xs text-muted-foreground">{vp.product.sku}</div>
                      </Link>
                    </TableCell>
                    <TableCell className="font-mono text-sm">{vp.vendorSku}</TableCell>
                    <TableCell className="text-right font-medium">
                      ${Number(vp.unitCost).toFixed(2)}
                    </TableCell>
                    <TableCell className="text-center">{vp.minOrderQty}</TableCell>
                    <TableCell className="text-center">{vp.orderMultiple}</TableCell>
                    <TableCell className="text-center">
                      {vp.casePackQty || "—"}
                    </TableCell>
                    <TableCell className="text-center">
                      {vp.leadTimeDays ? `${vp.leadTimeDays} days` : "Default"}
                    </TableCell>
                    <TableCell>
                      {vp.isPreferred && (
                        <Badge variant="outline" className="bg-yellow-100 text-yellow-800">
                          Preferred
                        </Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <p>No products linked to this vendor yet.</p>
              <p className="text-sm">Add products to track what you source from this vendor.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
