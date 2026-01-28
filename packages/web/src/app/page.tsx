"use client";

import Link from "next/link";
import { Package, MapPin, Layers, AlertTriangle, ArrowDown, ArrowUp, RefreshCw, ArrowLeftRight } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDashboardStats } from "@/hooks/use-dashboard";
import type { MovementType, StockMovement } from "@/lib/api";
import type { StockItem } from "@/hooks/use-stock-items";

function StatCardSkeleton() {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="h-4 w-24 bg-muted animate-pulse rounded" />
      </CardHeader>
      <CardContent>
        <div className="h-8 w-16 bg-muted animate-pulse rounded mb-1" />
        <div className="h-3 w-32 bg-muted animate-pulse rounded" />
      </CardContent>
    </Card>
  );
}

function TableRowSkeleton() {
  return (
    <tr className="border-b">
      <td className="p-4"><div className="h-4 w-16 bg-muted animate-pulse rounded" /></td>
      <td className="p-4"><div className="h-4 w-24 bg-muted animate-pulse rounded" /></td>
      <td className="p-4"><div className="h-4 w-20 bg-muted animate-pulse rounded" /></td>
      <td className="p-4 text-right"><div className="h-4 w-12 bg-muted animate-pulse rounded ml-auto" /></td>
      <td className="p-4 text-right"><div className="h-4 w-20 bg-muted animate-pulse rounded ml-auto" /></td>
    </tr>
  );
}

function MovementTypeIcon({ type }: { type: MovementType }) {
  const iconProps = { className: "h-4 w-4" };
  
  switch (type) {
    case "RECEIVE":
      return <ArrowDown {...iconProps} className="h-4 w-4 text-green-600" />;
    case "SHIP":
      return <ArrowUp {...iconProps} className="h-4 w-4 text-blue-600" />;
    case "ADJUST":
      return <RefreshCw {...iconProps} className="h-4 w-4 text-orange-600" />;
    case "TRANSFER":
      return <ArrowLeftRight {...iconProps} className="h-4 w-4 text-purple-600" />;
    default:
      return null;
  }
}

function MovementTypeBadge({ type }: { type: MovementType }) {
  const colors: Record<MovementType, string> = {
    RECEIVE: "bg-green-100 text-green-800",
    SHIP: "bg-blue-100 text-blue-800",
    ADJUST: "bg-orange-100 text-orange-800",
    TRANSFER: "bg-purple-100 text-purple-800",
  };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${colors[type]}`}>
      <MovementTypeIcon type={type} />
      {type}
    </span>
  );
}

function formatDate(dateString: string) {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function DashboardPage() {
  const { isLoading, stats, lowStockItems, recentMovements } = useDashboardStats();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of your inventory across all locations.
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          <>
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </>
        ) : (
          <>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Products</CardTitle>
                <Package className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats.totalProducts}</div>
                <p className="text-xs text-muted-foreground">Unique SKUs in catalog</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Units</CardTitle>
                <Layers className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats.totalUnits.toLocaleString()}</div>
                <p className="text-xs text-muted-foreground">Units in inventory</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Locations</CardTitle>
                <MapPin className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats.totalLocations}</div>
                <p className="text-xs text-muted-foreground">Active warehouses</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Low Stock</CardTitle>
                <AlertTriangle className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats.lowStockCount}</div>
                <p className="text-xs text-muted-foreground">Items need attention</p>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
          <CardDescription>Latest inventory movements and updates.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="p-4 text-left text-sm font-medium text-muted-foreground">Type</th>
                  <th className="p-4 text-left text-sm font-medium text-muted-foreground">Product</th>
                  <th className="p-4 text-left text-sm font-medium text-muted-foreground">Location</th>
                  <th className="p-4 text-right text-sm font-medium text-muted-foreground">Qty</th>
                  <th className="p-4 text-right text-sm font-medium text-muted-foreground">Date</th>
                </tr>
              </thead>
              <tbody>
                <TableRowSkeleton />
                <TableRowSkeleton />
                <TableRowSkeleton />
              </tbody>
            </table>
          ) : recentMovements.length === 0 ? (
            <p className="text-sm text-muted-foreground">No recent activity to display.</p>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="p-4 text-left text-sm font-medium text-muted-foreground">Type</th>
                  <th className="p-4 text-left text-sm font-medium text-muted-foreground">Product</th>
                  <th className="p-4 text-left text-sm font-medium text-muted-foreground">Location</th>
                  <th className="p-4 text-right text-sm font-medium text-muted-foreground">Qty</th>
                  <th className="p-4 text-right text-sm font-medium text-muted-foreground">Date</th>
                </tr>
              </thead>
              <tbody>
                {recentMovements.slice(0, 10).map((movement: StockMovement) => (
                  <tr key={movement.id} className="border-b">
                    <td className="p-4">
                      <MovementTypeBadge type={movement.type} />
                    </td>
                    <td className="p-4 text-sm">
                      {movement.stockItem?.product?.name ?? movement.stockItem?.product?.sku ?? "—"}
                    </td>
                    <td className="p-4 text-sm text-muted-foreground">
                      {movement.stockItem?.location?.name ?? "—"}
                    </td>
                    <td className="p-4 text-right text-sm font-medium">
                      {movement.quantity > 0 ? "+" : ""}{movement.quantity}
                    </td>
                    <td className="p-4 text-right text-sm text-muted-foreground">
                      {formatDate(movement.createdAt)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {/* Low Stock Alerts */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-orange-500" />
            Low Stock Alerts
          </CardTitle>
          <CardDescription>
            Items with less than 10 units available.{" "}
            <Link href="/inventory?lowStock=true" className="text-primary underline-offset-4 hover:underline">
              View all →
            </Link>
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              <div className="h-10 bg-muted animate-pulse rounded" />
              <div className="h-10 bg-muted animate-pulse rounded" />
            </div>
          ) : lowStockItems.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              🎉 All items are well stocked!
            </p>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="p-4 text-left text-sm font-medium text-muted-foreground">Product</th>
                  <th className="p-4 text-left text-sm font-medium text-muted-foreground">Location</th>
                  <th className="p-4 text-right text-sm font-medium text-muted-foreground">Available</th>
                </tr>
              </thead>
              <tbody>
                {lowStockItems.slice(0, 5).map((item: StockItem) => (
                  <tr key={item.id} className="border-b">
                    <td className="p-4 text-sm font-medium">
                      {item.product?.name ?? item.product?.sku ?? "Unknown"}
                    </td>
                    <td className="p-4 text-sm text-muted-foreground">
                      {item.location?.name ?? "Unknown"}
                    </td>
                    <td className="p-4 text-right">
                      <span className={`text-sm font-medium ${item.quantityAvailable === 0 ? "text-red-600" : "text-orange-600"}`}>
                        {item.quantityAvailable}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
