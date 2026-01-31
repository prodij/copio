import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { CreatePODialog } from "./create-dialog";

const API_URL = process.env.API_URL || "http://localhost:8001/api/v1";

interface PurchaseOrder {
  id: string;
  poNumber: string;
  status: string;
  notes: string | null;
  subtotal: number | null;
  total: number | null;
  orderedAt: string | null;
  expectedAt: string | null;
  receivedAt: string | null;
  createdAt: string;
  vendor: { id: string; name: string; code: string | null };
  destination: { id: string; name: string; type: string };
  _count: { lines: number };
}

async function getPurchaseOrders(): Promise<{ purchaseOrders: PurchaseOrder[]; total: number }> {
  const res = await fetch(`${API_URL}/purchase-orders`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch purchase orders");
  return res.json();
}

function formatDate(dateString: string | null) {
  if (!dateString) return "—";
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatCurrency(value: number | null) {
  if (value === null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    DRAFT: "bg-gray-100 text-gray-800",
    SUBMITTED: "bg-blue-100 text-blue-800",
    CONFIRMED: "bg-indigo-100 text-indigo-800",
    SHIPPED: "bg-purple-100 text-purple-800",
    PARTIAL: "bg-yellow-100 text-yellow-800",
    RECEIVED: "bg-green-100 text-green-800",
    CANCELLED: "bg-red-100 text-red-800",
  };
  return <Badge className={colors[status] || "bg-gray-100"} variant="outline">{status}</Badge>;
}

export default async function PurchaseOrdersPage() {
  const { purchaseOrders, total } = await getPurchaseOrders();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Purchase Orders</h1>
          <p className="text-muted-foreground">Manage orders to your vendors.</p>
        </div>
        <CreatePODialog />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Purchase Orders</CardTitle>
          <CardDescription>
            {total} purchase order{total !== 1 ? "s" : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>PO Number</TableHead>
                <TableHead>Vendor</TableHead>
                <TableHead>Destination</TableHead>
                <TableHead className="text-center">Lines</TableHead>
                <TableHead className="text-right">Total</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Expected</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {purchaseOrders.length > 0 ? (
                purchaseOrders.map((po) => (
                  <TableRow key={po.id} className="cursor-pointer hover:bg-muted/50">
                    <TableCell>
                      <Link href={`/purchase-orders/${po.id}`} className="font-medium hover:underline">
                        {po.poNumber}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <div className="font-medium">{po.vendor.name}</div>
                      {po.vendor.code && (
                        <div className="text-xs text-muted-foreground">{po.vendor.code}</div>
                      )}
                    </TableCell>
                    <TableCell>{po.destination.name}</TableCell>
                    <TableCell className="text-center">{po._count.lines}</TableCell>
                    <TableCell className="text-right font-medium">
                      {formatCurrency(po.total)}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={po.status} />
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(po.expectedAt)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(po.createdAt)}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                    No purchase orders yet. Create your first PO to start ordering from vendors.
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
