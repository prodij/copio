import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { CreateProductDialog } from "./create-dialog";

const API_URL = process.env.API_URL || "http://localhost:3002";

interface Product {
  id: string;
  sku: string;
  name: string;
  productType: string;
  status: string;
  brand: string | null;
  createdAt: string;
  images: Array<{ url: string }>;
  listings: Array<{ id: string; channel: string; status: string }>;
  _count: { variations: number };
}

async function getProducts(): Promise<Product[]> {
  const res = await fetch(`${API_URL}/products`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch products");
  return res.json();
}

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    DRAFT: "bg-gray-100 text-gray-800 hover:bg-gray-100",
    ACTIVE: "bg-green-100 text-green-800 hover:bg-green-100",
    ARCHIVED: "bg-orange-100 text-orange-800 hover:bg-orange-100",
  };
  return (
    <Badge className={colors[status] || "bg-gray-100"} variant="outline">
      {status.toLowerCase()}
    </Badge>
  );
}

function TypeBadge({ type }: { type: string }) {
  if (type === "SIMPLE") return null;
  const colors: Record<string, string> = {
    PARENT: "bg-purple-100 text-purple-800 hover:bg-purple-100",
    VARIATION: "bg-indigo-100 text-indigo-800 hover:bg-indigo-100",
  };
  return (
    <Badge className={colors[type] || "bg-gray-100"} variant="outline">
      {type.toLowerCase()}
    </Badge>
  );
}

function ChannelBadge({ channel }: { channel: string }) {
  const colors: Record<string, string> = {
    AMAZON: "bg-orange-100 text-orange-800",
    SHOPIFY: "bg-green-100 text-green-800",
    WALMART: "bg-blue-100 text-blue-800",
    EBAY: "bg-yellow-100 text-yellow-800",
  };
  return (
    <Badge className={`${colors[channel] || "bg-gray-100"} text-xs`} variant="outline">
      {channel}
    </Badge>
  );
}

export default async function ProductsPage() {
  const products = await getProducts();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Products</h1>
          <p className="text-muted-foreground">Manage your product catalog.</p>
        </div>
        <CreateProductDialog />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Product Catalog</CardTitle>
          <CardDescription>
            {products.length} product{products.length !== 1 ? "s" : ""} in your catalog
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-16"></TableHead>
                <TableHead>Product</TableHead>
                <TableHead>SKU</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Channels</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {products.length > 0 ? (
                products.map((product) => (
                  <TableRow key={product.id} className="cursor-pointer hover:bg-muted/50">
                    <TableCell>
                      {product.images?.[0]?.url ? (
                        <img
                          src={product.images[0].url}
                          alt=""
                          className="w-12 h-12 object-cover rounded"
                        />
                      ) : (
                        <div className="w-12 h-12 bg-muted rounded flex items-center justify-center text-muted-foreground text-xs">
                          No img
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      <Link href={`/products/${product.id}`} className="block">
                        <div className="font-medium hover:underline">{product.name}</div>
                        <div className="text-sm text-muted-foreground flex items-center gap-2">
                          {product.brand && <span>{product.brand}</span>}
                          <TypeBadge type={product.productType} />
                          {product._count?.variations > 0 && (
                            <span className="text-xs">({product._count.variations} variants)</span>
                          )}
                        </div>
                      </Link>
                    </TableCell>
                    <TableCell className="font-mono text-sm">{product.sku}</TableCell>
                    <TableCell>
                      <StatusBadge status={product.status} />
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {product.listings.length > 0 ? (
                          product.listings.map((listing) => (
                            <ChannelBadge key={listing.id} channel={listing.channel} />
                          ))
                        ) : (
                          <span className="text-muted-foreground text-sm">—</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(product.createdAt)}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                    No products yet. Create your first product to get started.
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
