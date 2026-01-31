import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InventoryTable } from "./inventory-table";

const API_URL = process.env.API_URL || 'http://localhost:8001/api/v1';

interface Product {
  id: string;
  sku: string;
  name: string;
}

interface Location {
  id: string;
  name: string;
}

interface StockItem {
  id: string;
  productId: string;
  locationId: string;
  quantityAvailable: number;
  quantityReserved: number;
  quantityInbound: number;
  costBasis: string | null;
  product: Product;
  location: Location;
}

async function getStockItems(): Promise<StockItem[]> {
  const res = await fetch(`${API_URL}/stock-items`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch stock items');
  return res.json();
}

async function getProducts(): Promise<Product[]> {
  const res = await fetch(`${API_URL}/products?pageSize=1000`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch products');
  const data = await res.json();
  return data.data || data; // Handle both paginated and legacy response
}

async function getLocations(): Promise<Location[]> {
  const res = await fetch(`${API_URL}/locations`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch locations');
  return res.json();
}

export default async function InventoryPage() {
  const [stockItems, products, locations] = await Promise.all([
    getStockItems(),
    getProducts(),
    getLocations(),
  ]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Inventory</h1>
          <p className="text-muted-foreground">
            Manage stock levels across all locations.
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Stock Levels</CardTitle>
          <CardDescription>
            Current inventory quantities by product and location. Click column headers to sort.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <InventoryTable 
            stockItems={stockItems} 
            products={products} 
            locations={locations} 
          />
        </CardContent>
      </Card>
    </div>
  );
}
