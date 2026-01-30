import Link from "next/link";
import { Suspense } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { CreateProductDialog } from "./create-dialog";
import { ProductFilters } from "@/components/product-filters";
import { SortableHeader } from "@/components/sortable-header";
import { Pagination } from "@/components/pagination";

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

interface ProductsResponse {
  data: Product[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
}

interface SearchParams {
  search?: string;
  status?: string;
  channel?: string;
  brand?: string;
  sortBy?: string;
  sortDir?: "asc" | "desc";
  page?: string;
  pageSize?: string;
}

async function getProducts(params: SearchParams): Promise<ProductsResponse> {
  const searchParams = new URLSearchParams();
  if (params.search) searchParams.set("search", params.search);
  if (params.status && params.status !== "all") searchParams.set("status", params.status);
  if (params.page) searchParams.set("page", params.page);
  if (params.pageSize) searchParams.set("pageSize", params.pageSize);
  
  const url = `${API_URL}/products?${searchParams.toString()}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch products");
  return res.json();
}

async function getAllBrands(): Promise<string[]> {
  // Get all products to extract brands (could optimize with dedicated endpoint)
  const res = await fetch(`${API_URL}/products?pageSize=1000`, { cache: "no-store" });
  if (!res.ok) return [];
  const data: ProductsResponse = await res.json();
  const brands = [...new Set(data.data.map((p) => p.brand).filter(Boolean))] as string[];
  brands.sort();
  return brands;
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
    DRAFT: "bg-gray-100 text-gray-800 hover:bg-gray-100 dark:bg-gray-800 dark:text-gray-300",
    ACTIVE: "bg-green-100 text-green-800 hover:bg-green-100 dark:bg-green-900 dark:text-green-300",
    ARCHIVED: "bg-orange-100 text-orange-800 hover:bg-orange-100 dark:bg-orange-900 dark:text-orange-300",
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
    PARENT: "bg-purple-100 text-purple-800 hover:bg-purple-100 dark:bg-purple-900 dark:text-purple-300",
    VARIATION: "bg-indigo-100 text-indigo-800 hover:bg-indigo-100 dark:bg-indigo-900 dark:text-indigo-300",
  };
  return (
    <Badge className={colors[type] || "bg-gray-100"} variant="outline">
      {type.toLowerCase()}
    </Badge>
  );
}

function ChannelBadge({ channel }: { channel: string }) {
  const colors: Record<string, string> = {
    AMAZON: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300",
    SHOPIFY: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
    WALMART: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
    EBAY: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  };
  return (
    <Badge className={`${colors[channel] || "bg-gray-100"} text-xs`} variant="outline">
      {channel}
    </Badge>
  );
}

export default async function ProductsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const [response, brands] = await Promise.all([
    getProducts(params),
    getAllBrands(),
  ]);

  const { data: products, pagination } = response;

  // Client-side filtering for channel and brand (not yet supported in API)
  let filteredProducts = products;
  
  if (params.channel && params.channel !== "all") {
    filteredProducts = filteredProducts.filter((p) =>
      p.listings.some((l) => l.channel === params.channel)
    );
  }
  
  if (params.brand && params.brand !== "all") {
    filteredProducts = filteredProducts.filter((p) => p.brand === params.brand);
  }
  
  // Client-side sorting
  const sortBy = params.sortBy || "createdAt";
  const sortDir = params.sortDir || "desc";
  
  filteredProducts.sort((a, b) => {
    let aVal: string | number | null;
    let bVal: string | number | null;
    
    switch (sortBy) {
      case "name":
        aVal = a.name.toLowerCase();
        bVal = b.name.toLowerCase();
        break;
      case "sku":
        aVal = a.sku.toLowerCase();
        bVal = b.sku.toLowerCase();
        break;
      case "brand":
        aVal = a.brand?.toLowerCase() || "";
        bVal = b.brand?.toLowerCase() || "";
        break;
      case "status":
        aVal = a.status;
        bVal = b.status;
        break;
      case "channels":
        aVal = a.listings.length;
        bVal = b.listings.length;
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
          <h1 className="text-3xl font-bold tracking-tight">Products</h1>
          <p className="text-muted-foreground">Manage your product catalog.</p>
        </div>
        <CreateProductDialog />
      </div>

      <Suspense fallback={<div className="h-10" />}>
        <ProductFilters brands={brands} />
      </Suspense>

      <Card>
        <CardHeader>
          <CardTitle>Product Catalog</CardTitle>
          <CardDescription>
            {filteredProducts.length} of {pagination.total} product{pagination.total !== 1 ? "s" : ""}
            {filteredProducts.length !== pagination.total && " (filtered)"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-16"></TableHead>
                <SortableHeader field="name">Product</SortableHeader>
                <SortableHeader field="sku">SKU</SortableHeader>
                <SortableHeader field="status">Status</SortableHeader>
                <SortableHeader field="channels">Channels</SortableHeader>
                <SortableHeader field="createdAt">Created</SortableHeader>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredProducts.length > 0 ? (
                filteredProducts.map((product) => (
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
                    {params.search || params.status || params.channel || params.brand
                      ? "No products found. Try adjusting your filters."
                      : "No products yet. Create your first product to get started."}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          <Pagination total={pagination.total} pageSize={pagination.pageSize} />
        </CardContent>
      </Card>
    </div>
  );
}
