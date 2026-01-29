import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Truck, MapPin, Calendar, Package, ExternalLink, Phone } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { POActions } from "./po-actions";
import { AddLineDialog } from "./add-line-dialog";
import { ReceiveDialog } from "./receive-dialog";
import { TrackingDialog } from "./tracking-dialog";
import { FollowUpDialog } from "./follow-up-dialog";
import { EditPODialog } from "./edit-po-dialog";
import { EditLineDialog } from "./edit-line-dialog";

const API_URL = process.env.API_URL || "http://localhost:3002";

interface POLine {
  id: string;
  productId: string;
  quantityOrdered: number;
  quantityReceived: number;
  unitCost: number;
  notes: string | null;
  product: {
    id: string;
    sku: string;
    name: string;
    images: Array<{ url: string }>;
  };
}

interface PurchaseOrder {
  id: string;
  poNumber: string;
  status: string;
  notes: string | null;
  subtotal: number | null;
  tax: number | null;
  shipping: number | null;
  total: number | null;
  orderedAt: string | null;
  expectedAt: string | null;
  shippedAt: string | null;
  receivedAt: string | null;
  createdAt: string;
  updatedAt: string;
  // Tracking
  carrier: string | null;
  trackingNumber: string | null;
  trackingUrl: string | null;
  shipmentStatus: string | null;
  vendorOrderNumber: string | null;
  vendorInvoiceNumber: string | null;
  // Follow-up
  lastContactedAt: string | null;
  nextFollowUpAt: string | null;
  followUpNotes: string | null;
  vendor: {
    id: string;
    name: string;
    code: string | null;
    contact: Record<string, unknown>;
    leadTimeDays: number;
  };
  destination: {
    id: string;
    name: string;
    type: string;
    address: Record<string, unknown>;
  };
  lines: POLine[];
}

async function getPurchaseOrder(id: string): Promise<PurchaseOrder | null> {
  const res = await fetch(`${API_URL}/purchase-orders/${id}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch purchase order");
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

function formatCurrency(value: number | null | undefined) {
  if (value === null || value === undefined) return "$0.00";
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
  return <Badge className={`${colors[status] || "bg-gray-100"} text-sm`} variant="outline">{status}</Badge>;
}

export default async function PurchaseOrderDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const po = await getPurchaseOrder(id);

  if (!po) {
    notFound();
  }

  const totalOrdered = po.lines.reduce((sum, line) => sum + line.quantityOrdered, 0);
  const totalReceived = po.lines.reduce((sum, line) => sum + line.quantityReceived, 0);
  const canReceive = po.status !== 'RECEIVED' && po.status !== 'CANCELLED' && po.status !== 'DRAFT';
  const canEdit = po.status === 'DRAFT';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/purchase-orders">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">{po.poNumber}</h1>
            <StatusBadge status={po.status} />
          </div>
          <p className="text-muted-foreground">
            Created {formatDate(po.createdAt)}
            {po.orderedAt && ` • Ordered ${formatDate(po.orderedAt)}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <EditPODialog po={po} />
          {po.status !== 'DRAFT' && po.status !== 'CANCELLED' && (
            <>
              <TrackingDialog po={po} />
              <FollowUpDialog po={po} />
            </>
          )}
          <POActions po={po} />
        </div>
      </div>

      {/* Tracking & Shipping Info */}
      {(po.trackingNumber || po.shipmentStatus || po.vendorOrderNumber) && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Truck className="h-5 w-5" /> Shipping & Tracking
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-4">
              {po.carrier && (
                <div>
                  <p className="text-sm text-muted-foreground">Carrier</p>
                  <p className="font-medium">{po.carrier}</p>
                </div>
              )}
              {po.trackingNumber && (
                <div>
                  <p className="text-sm text-muted-foreground">Tracking #</p>
                  <div className="flex items-center gap-2">
                    <p className="font-mono font-medium">{po.trackingNumber}</p>
                    {po.trackingUrl && (
                      <a href={po.trackingUrl} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="h-4 w-4 text-muted-foreground hover:text-foreground" />
                      </a>
                    )}
                  </div>
                </div>
              )}
              {po.shipmentStatus && (
                <div>
                  <p className="text-sm text-muted-foreground">Status</p>
                  <Badge variant="outline" className="mt-1">
                    {po.shipmentStatus.replace(/_/g, " ")}
                  </Badge>
                </div>
              )}
              {po.vendorOrderNumber && (
                <div>
                  <p className="text-sm text-muted-foreground">Vendor Order #</p>
                  <p className="font-medium">{po.vendorOrderNumber}</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Follow-up Info */}
      {(po.lastContactedAt || po.nextFollowUpAt) && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Phone className="h-5 w-5" /> Vendor Follow-up
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-3">
              {po.lastContactedAt && (
                <div>
                  <p className="text-sm text-muted-foreground">Last Contacted</p>
                  <p className="font-medium">{formatDate(po.lastContactedAt)}</p>
                </div>
              )}
              {po.nextFollowUpAt && (
                <div>
                  <p className="text-sm text-muted-foreground">Next Follow-up</p>
                  <p className="font-medium">{formatDate(po.nextFollowUpAt)}</p>
                </div>
              )}
              {po.followUpNotes && (
                <div className="md:col-span-3">
                  <p className="text-sm text-muted-foreground">Notes</p>
                  <p className="text-sm">{po.followUpNotes}</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-2">
              <Truck className="h-4 w-4" /> Vendor
            </CardDescription>
            <CardTitle className="text-lg">{po.vendor.name}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {po.vendor.code && `${po.vendor.code} • `}
              {po.vendor.leadTimeDays} day lead time
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-2">
              <MapPin className="h-4 w-4" /> Destination
            </CardDescription>
            <CardTitle className="text-lg">{po.destination.name}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{po.destination.type}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-2">
              <Calendar className="h-4 w-4" /> Expected
            </CardDescription>
            <CardTitle className="text-lg">{formatDate(po.expectedAt)}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {po.receivedAt ? `Received ${formatDate(po.receivedAt)}` : "Not yet received"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-2">
              <Package className="h-4 w-4" /> Progress
            </CardDescription>
            <CardTitle className="text-lg">
              {totalReceived} / {totalOrdered}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-green-500 h-2 rounded-full transition-all"
                style={{ width: `${totalOrdered > 0 ? (totalReceived / totalOrdered) * 100 : 0}%` }}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Order Lines */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Order Lines</CardTitle>
            <CardDescription>{po.lines.length} item{po.lines.length !== 1 ? "s" : ""}</CardDescription>
          </div>
          <div className="flex gap-2">
            {canReceive && <ReceiveDialog po={po} />}
            {canEdit && <AddLineDialog poId={po.id} vendorId={po.vendor.id} />}
          </div>
        </CardHeader>
        <CardContent>
          {po.lines.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[50px]"></TableHead>
                  <TableHead>Product</TableHead>
                  <TableHead className="text-right">Unit Cost</TableHead>
                  <TableHead className="text-center">Ordered</TableHead>
                  <TableHead className="text-center">Received</TableHead>
                  <TableHead className="text-right">Line Total</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {po.lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell>
                      {line.product.images[0] ? (
                        <img
                          src={line.product.images[0].url}
                          alt=""
                          className="h-10 w-10 rounded object-cover"
                        />
                      ) : (
                        <div className="h-10 w-10 rounded bg-muted flex items-center justify-center">
                          <Package className="h-4 w-4 text-muted-foreground" />
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      <Link href={`/products/${line.product.id}`} className="hover:underline">
                        <div className="font-medium">{line.product.name}</div>
                        <div className="text-xs text-muted-foreground">{line.product.sku}</div>
                      </Link>
                    </TableCell>
                    <TableCell className="text-right">
                      {formatCurrency(line.unitCost)}
                    </TableCell>
                    <TableCell className="text-center font-medium">
                      {line.quantityOrdered}
                    </TableCell>
                    <TableCell className="text-center">
                      <span className={line.quantityReceived >= line.quantityOrdered ? "text-green-600" : ""}>
                        {line.quantityReceived}
                      </span>
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {formatCurrency(line.quantityOrdered * line.unitCost)}
                    </TableCell>
                    <TableCell>
                      <EditLineDialog poId={po.id} line={line} canDelete={canEdit} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <p>No items in this order yet.</p>
              <p className="text-sm">Add products to this purchase order.</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Totals */}
      {po.lines.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex justify-end">
              <div className="w-64 space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Subtotal</span>
                  <span>{formatCurrency(po.subtotal)}</span>
                </div>
                {po.tax && Number(po.tax) > 0 && (
                  <div className="flex justify-between text-sm">
                    <span>Tax</span>
                    <span>{formatCurrency(po.tax)}</span>
                  </div>
                )}
                {po.shipping && Number(po.shipping) > 0 && (
                  <div className="flex justify-between text-sm">
                    <span>Shipping</span>
                    <span>{formatCurrency(po.shipping)}</span>
                  </div>
                )}
                <div className="flex justify-between font-medium text-lg border-t pt-2">
                  <span>Total</span>
                  <span>{formatCurrency(po.total)}</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Notes */}
      {po.notes && (
        <Card>
          <CardHeader>
            <CardTitle>Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">{po.notes}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
