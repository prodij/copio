import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { CreateVendorDialog } from "./create-dialog";

const API_URL = process.env.API_URL || "http://localhost:3002";

interface Vendor {
  id: string;
  name: string;
  code: string | null;
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

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default async function VendorsPage() {
  const vendors = await getVendors();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Vendors</h1>
          <p className="text-muted-foreground">Manage your suppliers and sourcing partners.</p>
        </div>
        <CreateVendorDialog />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Vendor Directory</CardTitle>
          <CardDescription>
            {vendors.length} vendor{vendors.length !== 1 ? "s" : ""} in your system
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Vendor</TableHead>
                <TableHead>Code</TableHead>
                <TableHead className="text-center">Products</TableHead>
                <TableHead className="text-center">Lead Time</TableHead>
                <TableHead>Payment Terms</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Added</TableHead>
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
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    No vendors yet. Add your first vendor to start tracking sourcing.
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
