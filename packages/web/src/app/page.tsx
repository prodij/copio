import Link from "next/link";
import { Package, MapPin, Layers, AlertTriangle, ArrowDown, ArrowUp, RefreshCw, ArrowLeftRight, FileText, DollarSign, Truck, Clock } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const API_URL = process.env.API_URL || 'http://localhost:8000/api/v1';

async function getProducts() {
  const res = await fetch(`${API_URL}/products?pageSize=1000`, { cache: 'no-store' });
  const data = await res.json();
  return data.data || data; // Handle both paginated and legacy response
}

async function getLocations() {
  const res = await fetch(`${API_URL}/locations`, { cache: 'no-store' });
  return res.json();
}

async function getStockItems() {
  const res = await fetch(`${API_URL}/stock-items`, { cache: 'no-store' });
  return res.json();
}

async function getMovements() {
  const res = await fetch(`${API_URL}/stock-movements`, { cache: 'no-store' });
  const data = await res.json();
  return data.data || data; // Handle both paginated and legacy response
}

async function getPurchaseOrders() {
  const res = await fetch(`${API_URL}/purchase-orders`, { cache: 'no-store' });
  if (!res.ok) return { purchaseOrders: [], total: 0 };
  return res.json();
}

function MovementTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    RECEIVE: "bg-green-100 text-green-800",
    SHIP: "bg-blue-100 text-blue-800",
    ADJUST: "bg-orange-100 text-orange-800",
    TRANSFER: "bg-purple-100 text-purple-800",
  };

  const icons: Record<string, React.ReactNode> = {
    RECEIVE: <ArrowDown className="h-3 w-3" />,
    SHIP: <ArrowUp className="h-3 w-3" />,
    ADJUST: <RefreshCw className="h-3 w-3" />,
    TRANSFER: <ArrowLeftRight className="h-3 w-3" />,
  };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${colors[type] || "bg-gray-100"}`}>
      {icons[type]}
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

export default async function DashboardPage() {
  const [products, locations, stockItems, movements, poData] = await Promise.all([
    getProducts(),
    getLocations(),
    getStockItems(),
    getMovements(),
    getPurchaseOrders(),
  ]);

  const totalUnits = stockItems.reduce((sum: number, item: any) => sum + item.quantityAvailable, 0);
  const lowStockItems = stockItems.filter((item: any) => item.quantityAvailable < 10);
  
  // Calculate inventory value
  const inventoryValue = stockItems.reduce((sum: number, item: any) => {
    const cost = parseFloat(item.costBasis) || 0;
    return sum + (cost * item.quantityAvailable);
  }, 0);

  // PO stats
  const purchaseOrders = poData.purchaseOrders || [];
  const openPOs = purchaseOrders.filter((po: any) => ['DRAFT', 'SUBMITTED', 'CONFIRMED'].includes(po.status));
  const inTransitPOs = purchaseOrders.filter((po: any) => po.status === 'SHIPPED');
  const totalPOValue = openPOs.reduce((sum: number, po: any) => sum + (parseFloat(po.total) || 0), 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of your inventory across all locations.
        </p>
      </div>

      {/* Stats Cards - Row 1: Inventory Overview */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Products</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{products.length}</div>
            <p className="text-xs text-muted-foreground">Unique SKUs in catalog</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Units</CardTitle>
            <Layers className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalUnits.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">Units in inventory</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Inventory Value</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${inventoryValue.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
            <p className="text-xs text-muted-foreground">Total cost basis</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Low Stock</CardTitle>
            <AlertTriangle className="h-4 w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">{lowStockItems.length}</div>
            <p className="text-xs text-muted-foreground">Items need attention</p>
          </CardContent>
        </Card>
      </div>

      {/* Stats Cards - Row 2: PO & Locations */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Open POs</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{openPOs.length}</div>
            <p className="text-xs text-muted-foreground">${totalPOValue.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })} pending</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">In Transit</CardTitle>
            <Truck className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{inTransitPOs.length}</div>
            <p className="text-xs text-muted-foreground">Shipments en route</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Locations</CardTitle>
            <MapPin className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{locations.length}</div>
            <p className="text-xs text-muted-foreground">Active warehouses</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Recent Activity</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{movements.length}</div>
            <p className="text-xs text-muted-foreground">Stock movements</p>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
          <CardDescription>Latest inventory movements and updates.</CardDescription>
        </CardHeader>
        <CardContent>
          {movements.length === 0 ? (
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
                {movements.slice(0, 10).map((movement: any) => (
                  <tr key={movement.id} className="border-b">
                    <td className="p-4">
                      <MovementTypeBadge type={movement.type} />
                    </td>
                    <td className="p-4 text-sm">
                      {movement.stockItem?.product?.name ?? "—"}
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
          {lowStockItems.length === 0 ? (
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
                {lowStockItems.slice(0, 5).map((item: any) => (
                  <tr key={item.id} className="border-b">
                    <td className="p-4 text-sm font-medium">
                      {item.product?.name ?? "Unknown"}
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
